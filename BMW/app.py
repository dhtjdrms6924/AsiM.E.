from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 15개 구역 준비
NUM_SPOTS = 15
reservations = {str(i): [] for i in range(1, NUM_SPOTS + 1)}

def overlaps(start, end, r_start, r_end):
    """겹치는지 확인"""
    return max(start, r_start) < min(end, r_end)

@app.route("/spots")
def all_spots():
    """모든 구역의 예약 가능 여부"""
    now = datetime.utcnow()
    start = now
    end = now + timedelta(minutes=30)

    result = []
    for spot_id, res_list in reservations.items():
        # 겹치는 예약 찾기
        conflict = [
            r for r in res_list
            if overlaps(start.timestamp(), end.timestamp(), r["start"], r["end"])
        ]
        available = len(conflict) == 0
        next_res = min((r["start"] for r in res_list if r["start"] > start.timestamp()), default=None)
        next_time = datetime.utcfromtimestamp(next_res).strftime("%H:%M") if next_res else None

        result.append({
            "spot_id": spot_id,
            "available": available,
            "next_reservation": next_time
        })
    return jsonify(result)

@app.route("/reservation_status/<spot_id>")
def reservation_status(spot_id):
    """특정 구역 예약 내역"""
    res_list = reservations.get(str(spot_id), [])
    return jsonify(res_list)

@app.route("/reserve", methods=["POST"])
def reserve():
    """예약 추가"""
    data = request.get_json()
    spot_id = str(data.get("spot_id"))
    start_str = data.get("start")
    duration = int(data.get("duration", 30))

    try:
        start_dt = datetime.fromisoformat(start_str)
    except Exception:
        return jsonify({"error": "Invalid start time"}), 400

    end_dt = start_dt + timedelta(minutes=duration)
    start_ts, end_ts = start_dt.timestamp(), end_dt.timestamp()

    # 겹침 검사
    for r in reservations[spot_id]:
        if overlaps(start_ts, end_ts, r["start"], r["end"]):
            return jsonify({"error": "이미 예약이 있습니다"}), 400

    new_res = {
        "start": start_ts,
        "end": end_ts,
        "duration": duration
    }
    reservations[spot_id].append(new_res)
    return jsonify({"message": "예약 성공", "reservation": new_res})

@app.route("/cancel", methods=["POST"])
def cancel():
    """예약 취소 (간단히 start 기준으로 취소)"""
    data = request.get_json()
    spot_id = str(data.get("spot_id"))
    start_ts = float(data.get("start"))

    res_list = reservations.get(spot_id, [])
    reservations[spot_id] = [r for r in res_list if r["start"] != start_ts]
    return jsonify({"message": "취소 완료"})
