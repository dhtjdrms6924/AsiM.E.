from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from datetime import datetime, timedelta
import secrets

# =========================
# 1. 앱 초기화 및 설정 (하나로 통합)
# =========================

app = Flask(__name__)

# 데모용 secret key 설정 (세션을 사용하지 않아도 CSRF 방어 등을 위해 필요)
app.secret_key = "super_secret_key"

# CORS 설정: 프론트엔드가 모든 도메인에서 쿠키를 포함하여 접근하도록 허용
# (운영 환경에서는 ["*"] 대신 Framer 도메인(예: "https://your-framer-site.framer.app")을 지정해야 보안상 안전합니다.)
CORS(app, resources={r"/api/*": {"origins": ["*"]}}, supports_credentials=True)

# 쿠키 설정: 크로스 사이트(Cross-site) 요청에서 쿠키를 보낼 수 있도록 설정
# Framer에서 API 서버로 요청할 때 필요합니다.
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,  # HTTPS 환경에서 True를 유지합니다. Render는 HTTPS를 사용합니다.
)


# =========================
# 2. 데이터 (데모용 In-Memory)
# =========================

# 주차장/지도 데이터 (변동 없음)
LOTS = {
    "gangnam": {
        "name": "강남역 1번 출구 주차장",
        "address": "서울특별시 강남구 테헤란로 123", # LotDetail.tsx 호환을 위해 address 추가
        "description": "강남역 초역세권 프리미엄 주차장입니다.", # LotDetail.tsx 호환을 위해 description 추가
        "pricePerHour": 3000, # LotDetail.tsx 호환을 위해 시간당 가격 필드 추가 (기존 base_price_per_min * 60)
        "image": "/static/images/gangnam_parking.png",
        "base_price_per_min": 50, # 3000원 / 60분
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
        "address": "서울특별시 마포구 양화로 161",
        "description": "홍대 번화가 중심에 위치한 주차장입니다.",
        "pricePerHour": 2400, # 40원 * 60분
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
        "address": "서울특별시 용산구 한강대로 405",
        "description": "KTX 이용객을 위한 넓은 공영 주차장입니다.",
        "pricePerHour": 3600, # 60원 * 60분
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
# 3. 유틸 함수 (Bearer Token 인증 방식 유지)
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
    """Authorization 헤더에서 토큰을 추출하여 사용자 이름 반환"""
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        token = h.split(" ", 1)[1]
        return tokens.get(token)
    return None


# =========================
# 4. API 라우트 (Bearer Token 인증 방식 유지 및 통합)
# =========================

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    u, p = data.get("username"), data.get("password")
    if u in users and users[u]["password"] == p:
        token = secrets.token_hex(16)
        tokens[token] = u
        return jsonify(token=token, points=users[u]["points"])
    # make_response 대신 jsonify 사용 (토큰 인증 섹션 유지)
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
                "address": lot["address"], # LotDetail 호환 필드 추가
                "description": lot["description"], # LotDetail 호환 필드 추가
                "pricePerHour": lot["pricePerHour"], # LotDetail 호환 필드 추가
                "image": lot["image"],
                "base_price_per_min": lot["base_price_per_min"],
                "estimated_points_per_hour": calculate_eco_points(lot_id, 0, 60),
                "map_coords": lot.get("map_coords"),
            }
        )
    return jsonify(
        {
            "query": q or "서울특별시",
            "map": {"image": loc["image"], "width": loc["map_width"], "height": loc["map_height"]},
            "lots": lots_payload,
        }
    )


@app.get("/api/parking/detail/<lot_id>") # Framer의 LotDetail.tsx에서 요청하는 경로로 수정 (원래 코드 `/api/parking/detail/{id}`에 맞춤)
def api_lot_detail(lot_id):
    lot = LOTS.get(lot_id)
    if not lot:
        return jsonify(error="not_found"), 404

    # LotDetail.tsx가 기대하는 필드 포함
    return jsonify(
        {
            "id": lot_id,
            "name": lot["name"],
            "address": lot["address"], 
            "description": lot["description"], 
            "pricePerHour": lot["pricePerHour"], 
            # 필요한 경우 상세 주차 공간 정보도 추가 가능
        }
    )


# 기존 '/api/lots/<lot_id>' 라우트는 '/api/parking/detail/<lot_id>' 라우트가 대체합니다.
# 기존의 '/api/lots/<lot_id>' 라우트처럼 상세 정보를 포함하는 버전
@app.get("/api/lots/<lot_id>")
def api_lot_map_detail(lot_id):
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


@app.post("/api/reserve")
def api_reserve():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    lot_id = d.get("lotId") # LotDetail.tsx에서 보낸 lotId 키에 맞춤
    start_time_str = d.get("startTime") # LotDetail.tsx에서 보낸 startTime 키에 맞춤
    duration_hours = int(d.get("durationHours", 0)) # LotDetail.tsx에서 보낸 durationHours 키에 맞춤

    # LotDetail.tsx에서 lotId를 숫자로 보내지만, LOTS 딕셔너리는 문자열 키를 사용하므로 문자열로 변환
    lot_id = str(lot_id) 
    spot_id = 0 # 상세 자리 예약이 아닌 전체 주차장 예약을 가정하고 0 사용

    if not all([lot_id, start_time_str]) or duration_hours <= 0:
        return jsonify(error="bad_request", message="필수 예약 정보가 누락되었습니다."), 400

    try:
        # LotDetail.tsx의 datetime-local 형식(YYYY-MM-DDTHH:MM)을 파싱
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
    except ValueError:
         return jsonify(error="bad_request", message="잘못된 시간 형식입니다. YYYY-MM-DDTHH:MM 형식이 필요합니다."), 400

    start_ts = int(start_dt.timestamp())
    end_ts = int((start_dt + timedelta(hours=duration_hours)).timestamp())
    duration_min = duration_hours * 60

    if start_ts < int(datetime.now().timestamp()) - 60: # 1분 여유
        return jsonify(error="past_time", message="과거 시간으로는 예약할 수 없습니다."), 400

    lot = LOTS.get(lot_id)
    if not lot:
        return jsonify(error="not_found", message="주차장 정보를 찾을 수 없습니다."), 404

    # 겹침 검사는 데모 목적상 생략하거나, 필요한 경우 주차장 전체를 검사하는 로직으로 대체 가능.
    # 현재는 상세 자리(spot) 없이 예약하므로, 복잡한 겹침 검사는 생략합니다.

    price = duration_min * lot["base_price_per_min"]
    points = calculate_eco_points(lot_id, spot_id, duration_min)

    reservation_id = secrets.token_hex(10) # 고유 ID 생성

    r = {
        "id": reservation_id,
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
    
    # LotDetail.tsx의 window.location.assign("/payment?reservationId=" + j.reservationId)에 맞춤
    return jsonify(reservationId=reservation_id, reservation=r)


@app.post("/api/payment/confirm")
def api_payment_confirm():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    # lot_id와 reservation_id를 모두 받지 않고 reservation_id만으로 모든 예약을 순회하여 찾습니다.
    rid = d.get("reservation_id")
    use_points = int(d.get("points_to_use", 0))

    target = None
    target_lot_id = None
    for lot_id, lst in reservations.items():
        for r in lst:
            if r["id"] == rid and r["user"] == user:
                target = r
                target_lot_id = lot_id
                break
        if target:
            break
            
    if not target:
        return jsonify(error="reservation_not_found"), 404

    price = target["original_price"]
    
    # 포인트 사용
    if use_points > 0:
        if users[user]["points"] < use_points:
            return jsonify(error="insufficient_points"), 400
        target["actual_price"] = max(0, price - use_points)
        users[user]["points"] -= use_points

    # 포인트 적립
    target["status"] = "paid"
    users[user]["points"] += target["points_earned"]
    
    return jsonify(
        reservation=target, 
        current_points=users[user]["points"], 
        lot_id=target_lot_id
    )

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
    out.sort(key=lambda x: x["start"], reverse=True) # 최신 예약부터 보이도록 역순 정렬
    return jsonify(reservations=out)

# 나머지 라우트('/reservation_status', '/calculate_estimates', '/api/reservations/cancel')는
# 중복이 없으므로 기존 코드를 그대로 유지합니다. (생략)

# (기존 reservation_status 함수 코드를 여기에 붙여넣음)
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

# (기존 calculate_estimates 함수 코드를 여기에 붙여넣음)
@app.get("/calculate_estimates/<lot_id>/<int:spot_id>/<int:duration_min>")
def calculate_estimates(lot_id, spot_id, duration_min):
    lot_info = LOTS.get(lot_id)
    if not lot_info:
        return jsonify(price=0, points=0)

    base_price_per_min = lot_info["base_price_per_min"]
    price = duration_min * base_price_per_min
    points = calculate_eco_points(lot_id, spot_id, duration_min)
    return jsonify(price=price, points=points)

# (기존 api_cancel 함수 코드를 여기에 붙여넣음)
@app.post("/api/reservations/cancel")
def api_cancel():
    user = auth_user()
    if not user:
        return jsonify(error="unauthorized"), 401

    d = request.get_json(silent=True) or {}
    lot_id = d.get("lot_id")
    rid = d.get("reservation_id") # rid를 문자열로 받도록 수정 (secrets.token_hex로 생성했기 때문)

    lst = reservations.get(lot_id, [])
    for i, r in enumerate(lst):
        if r["id"] == rid and r["user"] == user:
            if int(datetime.now().timestamp()) >= r["start"]:
                return jsonify(error="cannot_cancel_started"), 400
            del lst[i]
            return jsonify(ok=True)
    return jsonify(error="not_found"), 404

# =========================
# 5. 실행
# =========================

if __name__ == "__main__":
    # 개발용 로컬 실행 시
    app.run(debug=True, host="0.0.0.0", port=5001)

# Render에서 gunicorn이 실행할 때 필요한 'app' 객체가 파일 최상단에 정의되어 있으므로 문제 없음.
