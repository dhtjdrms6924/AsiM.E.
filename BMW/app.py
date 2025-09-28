from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = "super_secret_key"  # 데모 용
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# =========================
# 데이터 (데모용 In-Memory)
# =========================

# 주차장/지도 데이터
LOTS = {
    "gangnam": {
        "name": "강남역 1번 출구 주차장",
        "image": "/static/images/gangnam_parking.png",
        "base_price_per_min": 50,
        "traffic_level": 3,
        "spots": [
            {"id": 1, "coords": "228,116,300,188", "spot_density": 1},
            {"id": 2, "coords": "110,50,160,100", "spot_density": 2},
            {"id": 3, "coords": "170,50,220,100", "spot_density": 3},
            {"id": 4, "coords": "50,110,100,160", "spot_density": 1},
            {"id": 5, "coords": "110,110,160,160", "spot_density": 2},
            {"id": 6, "coords": "170,110,220,160", "spot_density": 3},
            {"id": 7, "coords": "50,170,100,220", "spot_density": 1},
            {"id": 8, "coords": "110,170,160,220", "spot_density": 2},
        ],
        "map_coords": [300, 250],
    },
    "hongdae": {
        "name": "홍대입구역 2번 출구 주차장",
        "image": "/static/images/hongdae_parking.png",
        "base_price_per_min": 40,
        "traffic_level": 4,
        "spots": [
            {"id": 1, "coords": "50,50,100,100", "spot_density": 2},
            {"id": 2, "coords": "110,50,160,100", "spot_density": 3},
            {"id": 3, "coords": "170,50,220,100", "spot_density": 2},
            {"id": 4, "coords": "50,110,100,160", "spot_density": 1},
            {"id": 5, "coords": "110,110,160,160", "spot_density": 2},
        ],
        "map_coords": [150, 100],
    },
    "seoul_station": {
        "name": "서울역 공영 주차장",
        "image": "/static/images/seoul_station_parking.png",
        "base_price_per_min": 60,
        "traffic_level": 2,
        "spots": [
            {"id": 1, "coords": "50,50,100,100", "spot_density": 1},
            {"id": 2, "coords": "110,50,160,100", "spot_density": 1},
            {"id": 3, "coords": "170,50,220,100", "spot_density": 2},
            {"id": 4, "coords": "50,110,100,160", "spot_density": 3},
            {"id": 5, "coords": "110,110,160,160", "spot_density": 2},
            {"id": 6, "coords": "170,110,220,160", "spot_density": 1},
            {"id": 7, "coords": "50,170,100,220", "spot_density": 2},
            {"id": 8, "coords": "110,170,160,220", "spot_density": 3},
            {"id": 9, "coords": "170,170,220,220", "spot_density": 1},
            {"id": 10, "coords": "50,230,100,280", "spot_density": 2},
        ],
        "map_coords": [200, 300],
    },
}

SEARCH_LOCATIONS = {
    "서울특별시": {
        "image": "/static/images/map_seoul_entire.jpg",
        "lots": ["gangnam", "hongdae", "seoul_station"],
        "map_width": 900,
        "map_height": 500,
    },
    "A": {
        "image": "/static/images/map_seoul_station.jpg",
        "lots": ["seoul_station"],
        "map_width": 600,
        "map_height": 400,
    },
    "B": {
        "image": "/static/images/map_gangnam.jpg",
        "lots": ["gangnam", "hongdae"],
        "map_width": 700,
        "map_height": 500,
    },
}

users = {
    "test_user1": {"points": 0, "password": "1234"},
    "admin": {"points": 100, "password": "password123"},
}

reservations = {}  # {lot_id: [ {id,user,spot,start,end,original_price,actual_price,points_earned,status} ]}

# 간단 토큰 인증
tokens = {}  # token -> username


# =========================
# 유틸 함수
# =========================
def check_overlapping(username, lot_id, spot_id, start_ts, end_ts):
    """사용자/자리 예약 겹침 검사"""
    lot_revs = reservations.get(lot_id, [])
    for r in lot_revs:
        # 동일 사용자의 시간 겹침
        if r["user"] == username and not (end_ts <= r["start"] or start_ts >= r["end"]):
            return True
        # 같은 자리의 시간 겹침
        if r["spot"] == spot_id and not (end_ts <= r["start"] or start_ts >= r["end"]):
            return "spot_taken"
    return False


def calculate_eco_points(lot_id, spot_id, duration_min):
    """친환경 포인트 계산(교통량/밀집도 기반, 데모 공식)"""
    lot_info = LOTS.get(lot_id)
    if not lot_info:
        return 0

    traffic_level = lot_info.get("traffic_level", 3)  # 1(한산) ~ 5(혼잡)

    if spot_id == 0:
        # 평균 밀집도
        total_density = sum(s["spot_density"] for s in lot_info["spots"])
        cnt = len(lot_info["spots"])
        spot_density = round(total_density / cnt) if cnt > 0 else 2
    else:
        spot_density = next((s["spot_density"] for s in lot_info["spots"] if s["id"] == spot_id), 2)

    # 교통량 역비례(1:100, 2:80, 3:60, 4:40, 5:20)
    base_points_per_hour = max(0, 120 - (traffic_level * 20))

    # 밀집도 보정(1:+20, 2:+0, 3:-10)
    density_points_per_hour = 20 if spot_density == 1 else (-10 if spot_density == 3 else 0)

    total_points_per_hour = base_points_per_hour + density_points_per_hour
    total_points = (total_points_per_hour / 60) * duration_min
    return max(0, round(total_points))


def auth_user():
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        token = h.split(" ", 1)[1]
        return tokens.get(token)
    return None


# =========================
# API (프론트=Framer)
# =========================

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    u, p = data.get("username"), data.get("password")
    if u in users and users[u]["password"] == p:
        token = secrets.token_hex(16)
        tokens[token] = u
        return jsonify(token=token, points=users[u]["points"])
    return jsonify(error="invalid_credentials"), 401


@app.get("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    loc = SEARCH_LOCATIONS.get(q) or SEARCH_LOCATIONS["서울특별시"]

    lots_payload = []
    for lot_id in loc["lots"]:
        lot = LOTS[lot_id]
        lots_payload.append(
            {
                "id": lot_id,
                "name": lot["name"],
                "image": lot["image"],
                "base_price_per_min": lot["base_price_per_min"],
                "estimated_points_per_hour": calculate_eco_points(lot_id, 0, 60),
                "map_coords": lot.get("map_coords"),  # [x, y] (지도 이미지 픽셀 기준)
            }
        )
    return jsonify(
        {
            "query": q or "서울특별시",
            "map": {"image": loc["image"], "width": loc["map_width"], "height": loc["map_height"]},
            "lots": lots_payload,
        }
    )


@app.get("/api/lots/<lot_id>")
def api_lot_detail(lot_id):
    lot = LOTS.get(lot_id)
    if not lot:
        return jsonify(error="not_found"), 404

    now_ts = int(datetime.now().timestamp())
    lot_res = reservations.get(lot_id, [])

    spots = []
    for s in lot["spots"]:
        occupied_now = any(r["spot"] == s["id"] and r["start"] <= now_ts < r["end"] for r in lot_res)
        # coords: "x1,y1,x2,y2" -> [x1,y1,x2,y2] 숫자 리스트로 변환
        x1, y1, x2, y2 = map(int, s["coords"].split(","))
        spots.append(
            {
                "id": s["id"],
                "coords": [x1, y1, x2, y2],
                "spot_density": s["spot_density"],
                "occupied_now": occupied_now,
            }
        )

    return jsonify(
        {
            "id": lot_id,
            "name": lot["name"],
            "image": lot["image"],
            "base_price_per_min": lot["base_price_per_min"],
            "traffic_level": lot["traffic_level"],
            "spots": spots,
        }
    )


@app.get("/reservation_status/<lot_id>/<int:spot_id>")
def reservation_status(lot_id, spot_id):
    now_dt = datetime.now()
    today_start_ts = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    today_end_ts = int(now_dt.replace(hour=23, minute=59, second=59, microsecond=999999).timestamp())

    lot_revs = reservations.get(lot_id, [])
    spot_reservations_today = [
        r
        for r in lot_revs
        if r["spot"] == spot_id and r["start"] <= today_end_ts and r["end"] >= today_start_ts
    ]

    # 현재 시각을 30분 단위로 올림
    current_time_rounded = now_dt.replace(second=0, microsecond=0)
    if current_time_rounded.minute > 30:
        current_time_rounded = current_time_rounded.replace(hour=current_time_rounded.hour + 1, minute=0)
    elif current_time_rounded.minute > 0:
        current_time_rounded = current_time_rounded.replace(minute=30)

    next_available_start_time = None
    slot_time = current_time_rounded
    while slot_time.date() == now_dt.date():
        slot_start_ts = int(slot_time.timestamp())
        slot_end_ts = int((slot_time + timedelta(minutes=30)).timestamp())
        is_occupied = any(not (slot_end_ts <= r["start"] or slot_start_ts >= r["end"]) for r in spot_reservations_today)
        if not is_occupied:
            next_available_start_time = slot_time
            break
        slot_time += timedelta(minutes=30)

    return jsonify(
        {
            "reserved": any(r["spot"] == spot_id and r["start"] <= int(now_dt.timestamp()) < r["end"] for r in lot_revs),
            "next_available_start_time": next_available_start_time.strftime("%H:%M") if next_available_start_time else None,
            "reservations": [{"start": r["start"], "end": r["end"], "user": r["user"]} for r in spot_reservations_today],
        }
    )


@app.get("/calculate_estimates/<lot_id>/<int:spot_id>/<int:duration_min>")
def calculate_estimates(lot_id, spot_id, duration_min):
    lot_info = LOTS.get(lot_id)
    if not lot_info:
        return jsonify(price=0, points=0)

    base_price_per_min = lot_info["base_price_per_min"]
    price = duration_min * base_price_per_min
    points = calculate_eco_points(lot_id, spot_id, duration_min)
    return jsonify(price=price, points=points)


@app.post("/api/reserve")
def api_reserve():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    lot_id = d.get("lot_id")
    spot_id = int(d.get("spot_id", 0))
    date_str = d.get("date")
    hour = int(d.get("hour", 0))
    minute = int(d.get("minute", 0))
    duration = int(d.get("duration_min", 0))

    if not all([lot_id, spot_id, date_str]) or duration <= 0:
        return jsonify(error="bad_request"), 400

    start_dt = datetime.strptime(f"{date_str} {hour}:{minute}", "%Y-%m-%d %H:%M")
    start_ts = int(start_dt.timestamp())
    end_ts = int((start_dt + timedelta(minutes=duration)).timestamp())

    if start_ts < int(datetime.now().timestamp()):
        return jsonify(error="past_time"), 400

    ov = check_overlapping(user, lot_id, spot_id, start_ts, end_ts)
    if ov is True:
        return jsonify(error="user_overlap"), 409
    if ov == "spot_taken":
        return jsonify(error="spot_taken"), 409

    lot = LOTS.get(lot_id)
    if not lot:
        return jsonify(error="not_found"), 404

    price = duration * lot["base_price_per_min"]
    points = calculate_eco_points(lot_id, spot_id, duration)

    r = {
        "id": int(datetime.now().timestamp() * 1000),
        "user": user,
        "spot": spot_id,
        "start": start_ts,
        "end": end_ts,
        "original_price": price,
        "actual_price": price,
        "points_earned": points,
        "status": "pending",
        "lot_id": lot_id,
    }
    reservations.setdefault(lot_id, []).append(r)
    return jsonify(reservation=r)


@app.post("/api/payment/confirm")
def api_payment_confirm():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    lot_id = d.get("lot_id")
    rid = int(d.get("reservation_id", 0))
    use_points = int(d.get("points_to_use", 0))

    lst = reservations.get(lot_id, [])
    r = next((x for x in lst if x["id"] == rid and x["user"] == user), None)
    if not r:
        return jsonify(error="not_found"), 404

    price = r["original_price"]
    if use_points > 0:
        if users[user]["points"] < use_points:
            return jsonify(error="insufficient_points"), 400
        r["actual_price"] = max(0, price - use_points)
        users[user]["points"] -= use_points

    r["status"] = "paid"
    users[user]["points"] += r["points_earned"]
    return jsonify(reservation=r, current_points=users[user]["points"])


@app.get("/api/reservations")
def api_reservations():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    out = []
    for lot_id, lst in reservations.items():
        for r in lst:
            if r["user"] == user:
                out.append({**r, "lot_id": lot_id})
    out.sort(key=lambda x: x["start"])
    return jsonify(reservations=out)


@app.post("/api/reservations/cancel")
def api_cancel():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    lot_id = d.get("lot_id")
    rid = int(d.get("reservation_id", 0))

    lst = reservations.get(lot_id, [])
    for i, r in enumerate(lst):
        if r["id"] == rid and r["user"] == user:
            if int(datetime.now().timestamp()) >= r["start"]:
                return jsonify(error="cannot_cancel_started"), 400
            del lst[i]
            return jsonify(ok=True)
    return jsonify(error="not_found"), 404


if __name__ == "__main__":
    # 개발용 실행
    app.run(debug=True, host="0.0.0.0", port=5001)
