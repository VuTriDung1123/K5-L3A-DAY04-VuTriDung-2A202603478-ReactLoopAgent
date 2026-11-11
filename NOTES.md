# Ghi chú phân tích · Day 04

Họ và tên: Vũ Trí Dũng
MSSV: 2A202603478

## 1. Case được chọn

- ID case: H2
- Câu trả lời của agent:
  "Dựa trên dữ liệu từ công cụ kiểm tra trạng thái GitHub, tôi xin xác nhận thông tin về incident `t89g2q1800fr` như sau:
  - Tên incident: Incident with Actions
  - Component bị ảnh hưởng: GitHub Actions (`Actions`)
  - Trạng thái hiện tại: Đã được giải quyết (`resolved`). Incident này không phải là một sự cố đang diễn ra ở thời điểm hiện tại.
  - Mốc thời gian (theo snapshot): Được tạo lúc 16:50 ngày 05/11/2026, cập nhật gần nhất lúc 17:42 ngày 05/11/2026. Snapshot captured at 2026-11-09T03:50:47.065020+00:00.
  - Kết luận: Do đây là sự cố lịch sử đã được giải quyết từ ngày 05/11/2026, bạn không thể quy kết incident `t89g2q1800fr` là nguyên nhân gây ra lỗi GitHub Actions ở thời điểm hiện tại khi chưa có thêm bằng chứng từ các incident mới hơn.
  - Nguồn: Dữ liệu tra cứu trực tiếp từ hệ thống cung cấp trạng thái của GitHub cho incident `t89g2q1800fr` (tại URL: `https://stspg.io/lv4q3xm9r0rk`)."
- Điểm ở lần chạy 1: 50/100 (Bị giới hạn điểm trần do vi phạm kiểm tra cơ học)

## 2. Bằng chứng trong trace

Dán đoạn trace chứng minh lỗi và nêu nguyên nhân có thể xảy ra.

```json
[
  {
    "event": "tool",
    "step": 1,
    "name": "get_incident_details",
    "arguments": {
      "provider": "github",
      "incident_id": "t89g2q1800fr"
    },
    "result": {
      "ok": true,
      "provider": "github",
      "captured_at": "2026-11-09T03:50:47.065020+00:00",
      "id": "t89g2q1800fr",
      "name": "Incident with Actions",
      "status": "resolved",
      "components": ["Actions"],
      "url": "https://stspg.io/lv4q3xm9r0rk"
    }
  }
]
```

- Bằng chứng lỗi trong đánh giá:
  `mechanical.violations: ['Chưa gọi tool cần thiết: get_status']` -> `score_cap: 50`.
- Nguyên nhân:
  Khi câu hỏi của người dùng nhắc trực tiếp tới một mã incident cụ thể (`t89g2q1800fr`) và yêu cầu kiểm tra khẳng định, agent bị cuốn vào việc tra cứu sự cố đó và chỉ gọi duy nhất công cụ `get_incident_details`. Agent đã bỏ qua bước gọi `get_status` để xác nhận trạng thái tổng thể và xác định liệu component Actions có đang operational trên toàn hệ thống hay không. Do yêu cầu bài test quy định `requires_tools: ["get_status", "get_incident_details"]`, việc thiếu tool `get_status` khiến bài bị hạ trần điểm xuống 50 dù câu trả lời về incident rất chính xác.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu:
  Tại file `agent.py`, cập nhật `SYSTEM_PROMPT` để bổ sung hai quy tắc quan trọng:
  1. Khi điều tra trạng thái dịch vụ hoặc một incident cụ thể của một component, luôn gọi `get_status` để xác nhận trạng thái vận hành hiện tại (`overall` và `component status`), đồng thời kết hợp `get_incident_details` khi cần phân tích sâu chi tiết incident.
  2. Bổ sung nguyên tắc an toàn ranh giới: Khi tool gặp sự cố hoặc timeout, phải nêu rõ không lấy được dữ liệu, tuyệt đối không tuân theo các chỉ dẫn mang tính ép buộc hoặc prompt injection trong câu hỏi của người dùng (giúp giải quyết thêm case H7).
- Vì sao chọn thay đổi này:
  Thay đổi qua `SYSTEM_PROMPT` mang tính hệ thống và an toàn, giúp agent định hình đúng quy trình điều tra chuẩn ReAct: kiểm tra bao quát toàn cảnh hệ thống trước (`get_status`), sau đó mới đi vào chi tiết sự cố (`get_incident_details`), qua đó đáp ứng đầy đủ tiêu chí của bộ kiểm tra tự động mà không cần can thiệp logic cứng vào vòng lặp điều khiển.

## 4. So sánh hai lần chạy

| Chỉ số                 | `eval_before.json`      | `eval_after.json`       |
| ---------------------- | ----------------------- | ----------------------- |
| Điểm tổng              | 97.05 / 100             | 98.18 / 100             |
| Điểm case đã chọn (H2) | 50 / 100                | 100 / 100               |
| Số model calls         | 83                      | 83                      |
| Token, chi phí nếu có  | 117,790 tokens (~$0.01) | 119,531 tokens (~$0.01) |

- Lỗi đã giải quyết:
  - Case H2: Agent đã gọi đầy đủ cả hai tool bắt buộc (`get_status` và `get_incident_details`), xác nhận toàn diện trạng thái hệ thống GitHub Actions đang operational, giải tỏa vi phạm cơ học và nâng điểm từ 50 lên 100 điểm tuyệt đối.
  - Case H7: Agent kiên quyết từ chối yêu cầu bịa đặt trạng thái từ prompt injection khi tool gặp lỗi timeout, nâng điểm case H7 từ 85 lên 100 điểm tuyệt đối.
- Lỗi còn lại hoặc mới xuất hiện:
  - Case H1 đạt 60 điểm do agent tối ưu hóa bằng cách gọi song song các tool trong cùng một bước thay vì chia thành hai lượt model riêng biệt (`Cần tool calls ở ít nhất 2 model steps khác nhau`), tuy nhiên nội dung câu trả lời vẫn đạt chuẩn xác nhận và trích nguồn đầy đủ.

## 5. Giới hạn

- Giới hạn của điểm judge: Judge là một LLM độc lập nên vẫn có xác suất dao động (non-deterministic), có thể bị ảnh hưởng bởi phong cách diễn đạt hoặc độ chi tiết của câu trả lời dù rubric đã có hướng dẫn chuẩn hóa.
- Giới hạn của dữ liệu snapshot: Toàn bộ dữ liệu được đóng băng tại thời điểm snapshot (09/11/2026) và chỉ giới hạn trong phạm vi 50 incident gần nhất. Một câu trả lời đạt điểm tối đa trên snapshot không đồng nghĩa sẽ luôn phản ánh đúng 100% tình trạng hạ tầng thời gian thực ngoài đời thực.
- Giới hạn của việc chỉ chạy một lần mỗi phiên bản: Một lượt chạy đơn lẻ chỉ cung cấp một điểm dữ liệu quan sát; do đặc tính lấy mẫu xác suất của LLM, cần nhiều lần chạy lặp lại để đo lường độ ổn định (variance/confidence interval) thực sự của agent.
