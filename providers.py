"""Bốn provider cùng một interface. Không chứa agent loop."""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

CONFIG = {
    'openai': ('OPENAI_API_KEY', 'https://api.openai.com/v1/chat/completions'),
    'gemini': ('GEMINI_API_KEY', 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'),
    'openrouter': ('OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/chat/completions'),
    'anthropic': ('ANTHROPIC_API_KEY', 'https://api.anthropic.com/v1/messages'),
}


def post_json(url, headers, payload, max_retries=6):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', **headers})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            # Do not print response bodies: they may contain account or request data.
            raise RuntimeError(f'Provider trả HTTP {exc.code}; kiểm tra model, key và quota.') from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f'Không kết nối được provider: {exc.reason}') from exc


class Provider:
    """complete(messages, schemas) -> {message, calls, finish, usage}.

    messages: system/user/assistant/tool theo format Chat Completions. message trả về
    cần được append nguyên vẹn; tool result có role, tool_call_id, content (JSON string).
    """
    _key_indices = {}

    def __init__(self, name, model):
        if name not in CONFIG:
            raise ValueError(f'Provider không hợp lệ: {name}')
        if not model:
            raise ValueError('Cần đặt MODEL là model có hỗ trợ tool calling.')
        self.name, self.model = name, model
        key_name, self.url = CONFIG[name]

        keys = []
        raw_key = os.getenv(key_name)
        if raw_key:
            for k in raw_key.replace(',', '\n').splitlines():
                k = k.strip()
                if k and k != 'YOUR_KEY' and k not in keys:
                    keys.append(k)
        env_file = Path(__file__).resolve().parent / '.env'
        if env_file.exists():
            for line in env_file.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith(f'set {key_name}=') or line.startswith(f'{key_name}='):
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if val and val != 'YOUR_KEY' and val not in keys:
                        keys.append(val)
        if not keys:
            raise ValueError(f'Thiếu {key_name}; xem README.md.')
        self.keys = keys
        self.key = keys[0]

    def complete(self, messages, schemas):
        if self.name == 'anthropic':
            return self._anthropic(messages, schemas)

        candidate_models = [self.model]
        if self.name == 'gemini':
            for alt in ('gemini-flash-lite-latest', 'gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-3.5-flash'):
                if alt not in candidate_models:
                    candidate_models.append(alt)

        last_exc = None
        for m in candidate_models:
            payload = {'model': m, 'messages': messages}
            if schemas:
                payload['tools'] = schemas
            for attempt in range(len(self.keys) * 2):
                idx = Provider._key_indices.get(self.name, 0) % len(self.keys)
                key = self.keys[idx]
                try:
                    data = post_json(self.url, {'Authorization': f'Bearer {key}'}, payload, max_retries=1)
                    choice = data['choices'][0]
                    message = choice['message']
                    calls = [{'id': c['id'], 'name': c['function']['name'], 'arguments': c['function']['arguments']} for c in message.get('tool_calls', [])]
                    return {'message': message, 'calls': calls, 'finish': choice.get('finish_reason'), 'usage': data.get('usage', {})}
                except RuntimeError as exc:
                    last_exc = exc
                    if any(err in str(exc) for err in ('429', '500', '502', '503', '504')):
                        if len(self.keys) > 1:
                            Provider._key_indices[self.name] = idx + 1
                        time.sleep(2)
                        continue
                    raise
        if last_exc:
            raise last_exc

    def _anthropic(self, messages, schemas):
        system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
        native = []
        for m in messages:
            if m['role'] == 'system':
                continue
            if m['role'] == 'assistant':
                blocks = []
                if m.get('content'):
                    blocks.append({'type': 'text', 'text': m['content']})
                for call in m.get('tool_calls', []):
                    blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'], 'input': json.loads(call['function']['arguments'])})
                native.append({'role': 'assistant', 'content': blocks})
            elif m['role'] == 'tool':
                block = {'type': 'tool_result', 'tool_use_id': m['tool_call_id'], 'content': m['content']}
                if native and native[-1]['role'] == 'user' and isinstance(native[-1]['content'], list):
                    native[-1]['content'].append(block)
                else:
                    native.append({'role': 'user', 'content': [block]})
            else:
                native.append({'role': 'user', 'content': m['content']})
        tools = [{'name': x['function']['name'], 'description': x['function']['description'], 'input_schema': x['function']['parameters']} for x in schemas]
        payload = {'model': self.model, 'max_tokens': 1024, 'system': system, 'messages': native}
        if tools:
            payload['tools'] = tools
        data = post_json(self.url, {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}, payload)
        blocks = data['content']
        calls = [{'id': b['id'], 'name': b['name'], 'arguments': json.dumps(b['input'], ensure_ascii=False)} for b in blocks if b['type'] == 'tool_use']
        text = '\n'.join(b['text'] for b in blocks if b['type'] == 'text')
        message = {'role': 'assistant', 'content': text or None}
        if calls:
            message['tool_calls'] = [{'id': c['id'], 'type': 'function', 'function': {'name': c['name'], 'arguments': c['arguments']}} for c in calls]
        reason = {'end_turn': 'stop', 'tool_use': 'tool_calls', 'max_tokens': 'length'}.get(data.get('stop_reason'), data.get('stop_reason'))
        return {'message': message, 'calls': calls, 'finish': reason, 'usage': data.get('usage', {})}
