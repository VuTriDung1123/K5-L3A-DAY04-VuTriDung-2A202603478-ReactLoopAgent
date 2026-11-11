"""
Web Demo & Interactive Dashboard for Status Investigation Agent (Day 04 Lab)
Author: Vũ Trí Dũng - 2A202603478
"""

import json
import os
from pathlib import Path
import sys
import webbrowser
from flask import Flask, jsonify, render_template, request

# Ensure local modules are accessible
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evals'))

from agent import run_agent
from bonus.tools import BonusTools
from providers import Provider
from status_tools import StatusTools

app = Flask(__name__, template_folder='templates', static_folder='static')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/data')
def get_data():
    """Load eval_before, eval_after, eval_bonus, and NOTES.md."""
    data = {}
    before_path = ROOT / 'eval_before.json'
    after_path = ROOT / 'eval_after.json'
    bonus_path = ROOT / 'eval_bonus.json'
    notes_path = ROOT / 'NOTES.md'

    if before_path.exists():
        try:
            data['before'] = json.loads(before_path.read_text(encoding='utf-8'))
        except Exception as e:
            data['before'] = {'error': str(e)}

    if after_path.exists():
        try:
            data['after'] = json.loads(after_path.read_text(encoding='utf-8'))
        except Exception as e:
            data['after'] = {'error': str(e)}

    if bonus_path.exists():
        try:
            data['bonus'] = json.loads(bonus_path.read_text(encoding='utf-8'))
        except Exception as e:
            data['bonus'] = {'error': str(e)}

    if notes_path.exists():
        data['notes'] = notes_path.read_text(encoding='utf-8')

    return jsonify(data)


@app.route('/api/ask', methods=['POST'])
def ask_agent():
    """Execute live ReAct agent loop on user request."""
    payload = request.get_json() or {}
    question = payload.get('question', '').strip()
    if not question:
        return jsonify({'ok': False, 'error': 'Vui lòng nhập câu hỏi.'}), 400

    mode = payload.get('mode', 'snapshot')
    bonus = bool(payload.get('bonus', False))
    max_steps = int(payload.get('max_steps', 8))
    provider_name = os.getenv('PROVIDER', 'gemini')
    model_name = os.getenv('MODEL', 'gemini-flash-lite-latest')

    try:
        provider = Provider(provider_name, model_name)
        tools = BonusTools(mode) if bonus else StatusTools(mode)
        result = run_agent(question, provider, tools, max_steps=max_steps)
        return jsonify({'ok': True, 'result': result})
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'{type(exc).__name__}: {str(exc)}'}), 500


def main():
    port = int(os.getenv('PORT', 5000))
    print(f'Starting Status Agent Web Demo on http://localhost:{port}...')
    # Open browser automatically if not in headless environment
    try:
        webbrowser.open(f'http://localhost:{port}')
    except Exception:
        pass
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()

