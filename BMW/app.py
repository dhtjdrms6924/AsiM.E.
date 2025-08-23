from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = 'super_secret_key' # 실제 운영 환경에서는 더 복잡한 키를 사용하세요.

# 주차장 데이터 (예시)
# 'traffic_level': 1~5 (1: 한산, 5: 매우 혼잡)
# 'spot_density': 1~3 (1: 널널함, 3: 빽빽함)
# 'map_coords': [x, y] - 이 주차장이 지역 지도 이미지 상에 표시될 대략적인 좌표 (픽셀)
LOTS = {
    "gangnam": {
        "name": "강남역 1번 출구 주차장",
        "image": "/static/images/gangnam_parking.png", # 주차장 도면 이미지 (placeholder)
        "base_price_per_min": 50, # 분당 기본 가격
        "traffic_level": 3, # 현재 교통량 혼잡도 (시뮬레이션)
        "spots": [
            {"id": 1, "coords": "37,62,106,128", "spot_density": 1}, 
            {"id": 2, "coords": "109,62,176,128", "spot_density": 2},
            {"id": 3, "coords": "180,62,246,128", "spot_density": 3},
            {"id": 4, "coords": "37,132,106,198", "spot_density": 1},
            {"id": 5, "coords": "109,132,176,198", "spot_density": 2},
            {"id": 6, "coords": "180,132,246,198", "spot_density": 3},
            {"id": 7, "coords": "37,202,106,268", "spot_density": 1},
            {"id": 8, "coords": "109,202,176,268", "spot_density": 2},
            {"id": 9, "coords": "180,202,246,268", "spot_density": 1},
            {"id": 10, "coords": "37,272,106,338", "spot_density": 2},
            {"id": 11, "coords": "260,50,310,120", "spot_density": 3},
            {"id": 12, "coords": "260,125,310,195", "spot_density": 3},
            {"id": 13, "coords": "260,200,310,270", "spot_density": 3},
            {"id": 14, "coords": "260,275,310,345", "spot_density": 2},
            {"id": 15, "coords": "260,350,310,420", "spot_density": 2},
            {"id": 16, "coords": "260,425,310,495", "spot_density": 2},
            {"id": 17, "coords": "450,40,520,150", "spot_density": 1},
            {"id": 18, "coords": "450,160,520,270", "spot_density": 1},
            {"id": 19, "coords": "450,280,520,390", "spot_density": 1},
            {"id": 20, "coords": "530,40,600,150", "spot_density": 1},
            {"id": 21, "coords": "530,160,600,270", "spot_density": 1},
            {"id": 22, "coords": "600,155,670,265", "spot_density": 1, "is_disabled": True},
        ],
        "map_coords": [300, 250]
    },
    "hongdae": {
        "name": "홍대입구역 2번 출구 주차장",
        "image": "/static/images/hongdae_parking.png", # 주차장 도면 이미지 (placeholder)
        "base_price_per_min": 40,
        "traffic_level": 4,
        "spots": [
            {"id": 1, "coords": "50,50,100,100", "spot_density": 2},
            {"id": 2, "coords": "110,50,160,100", "spot_density": 3},
            {"id": 3, "coords": "170,50,220,100", "spot_density": 2},
            {"id": 4, "coords": "50,110,100,160", "spot_density": 1},
            {"id": 5, "coords": "110,110,160,160", "spot_density": 2},
        ],
        "map_coords": [150, 100] # 강남 지도 (map_gangnam.jpg) 상의 대략적인 위치 (예시)
    },
    "seoul_station": {
        "name": "서울역 공영 주차장",
        "image": "/static/images/seoul_station_parking.png", # 주차장 도면 이미지 (placeholder)
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
        "map_coords": [200, 300] # 서울역 지도 (map_seoul_station.jpg) 상의 대략적인 위치
    }
}

# 실제 지도를 불러오기 어렵기 때문에, 특정 검색 키워드에 매핑되는 지도를 정의
SEARCH_LOCATIONS = {
    "서울특별시": {
        "image": "/static/images/map_seoul_entire.jpg", # 서울특별시 전체 지도
        "lots": ["gangnam", "hongdae", "seoul_station"], # 모든 주차장 포함 (기본 지도)
        "map_width": 900, # 이미지 원본 너비 (예시)
        "map_height": 500 # 이미지 원본 높이 (예시)
    },
    "A": { # 서울역
        "image": "/static/images/map_seoul_station.jpg", # 서울역 지도
        "lots": ["seoul_station"], # 서울역 주차장만
        "map_width": 600, # 이미지 원본 너비 (예시)
        "map_height": 400 # 이미지 원본 높이 (예시)
    },
    "B": { # 강남
        "image": "/static/images/map_gangnam.jpg", # 강남 지도
        "lots": ["gangnam", "hongdae"], # 강남 및 홍대 주차장
        "map_width": 700, # 이미지 원본 너비 (예시)
        "map_height": 500 # 이미지 원본 높이 (예시)
    }
}

# 사용자 정보와 예약 정보 (인메모리 저장 - 실제 서비스에서는 DB 사용)
# 사용자별 포인트 정보 추가
# 비밀번호 기능 추가
# **경고: 보안을 위해 실제 서비스에서는 비밀번호를 해시하여 저장해야 합니다.**
users = {
    "test_user1": {"points": 0, "password": "1234"},
    "admin": {"points": 100, "password": "password123"},
}
reservations = {} # {lot_id: [{id, user, spot, start, end, price, points_earned}]}

@app.template_filter('datetimeformat')
def datetimeformat(value):
    # value가 datetime 객체인지, timestamp인지 확인하여 처리
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M')
    return value.strftime('%Y-%m-%d %H:%M')


@app.template_filter('datetimeformat_date')
def datetimeformat_date(value):
    # value가 datetime 객체인지, timestamp인지 확인하여 처리
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).strftime('%Y-%m-%d')
    return value.strftime('%Y-%m-%d')


def check_overlapping(username, lot_id, spot_id, start_ts, end_ts):
    lot_revs = reservations.get(lot_id, [])
    for r in lot_revs:
        # 동일한 사용자가 동일 시간대에 다른 예약을 시도하는 경우 (기존 코드 유지)
        if r['user'] == username:
            if not (end_ts <= r['start'] or start_ts >= r['end']):
                return True
        # 다른 사용자가 동일한 자리를 예약하려고 하는 경우
        if r['spot'] == spot_id:
            if not (end_ts <= r['start'] or start_ts >= r['end']):
                return "spot_taken"
    return False

# 친환경 포인트 계산 함수
def calculate_eco_points(lot_id, spot_id, duration_min):
    lot_info = LOTS.get(lot_id)
    if not lot_info:
        return 0

    traffic_level = lot_info.get("traffic_level", 3) # 1~5 (1: 한산, 5: 매우 혼잡)
    
    # spot_id가 0일 경우 (검색 결과 페이지에서 예상 포인트 표시 시)는 평균 밀집도를 사용
    if spot_id == 0:
        # 모든 스팟의 밀집도를 고려한 평균 밀집도 (예시)
        total_density = sum(s['spot_density'] for s in lot_info['spots'])
        spot_count = len(lot_info['spots'])
        spot_density = round(total_density / spot_count) if spot_count > 0 else 2
    else:
        spot_density = next((s['spot_density'] for s in lot_info['spots'] if s['id'] == spot_id), 2) # 1~3 (1: 널널함, 3: 빽빽함)

    # 기본 포인트 (시간당) - 교통량에 반비례
    # 교통량 1: 100포인트/시간, 2: 80, 3: 60, 4: 40, 5: 20
    base_points_per_hour = max(0, 120 - (traffic_level * 20)) # 1시간 기준
    
    # 주차 공간 밀집도에 따른 추가 포인트 (널널할수록 추가)
    # 밀집도 1: +20포인트/시간, 2: +0, 3: -10
    density_points_per_hour = 0
    if spot_density == 1:
        density_points_per_hour = 20
    elif spot_density == 3:
        density_points_per_hour = -10

    total_points_per_hour = base_points_per_hour + density_points_per_hour
    
    # 분 단위로 변환 및 계산
    total_points = (total_points_per_hour / 60) * duration_min
    return max(0, round(total_points)) # 음수 방지 및 반올림


@app.route("/calculate_estimates/<lot_id>/<int:spot_id>/<int:duration_min>")
def calculate_estimates(lot_id, spot_id, duration_min):
    lot_info = LOTS.get(lot_id)
    if not lot_info:
        return jsonify(price=0, points=0)

    base_price_per_min = lot_info['base_price_per_min']
    price = duration_min * base_price_per_min
    points = calculate_eco_points(lot_id, spot_id, duration_min)
    
    return jsonify(price=price, points=points)


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # users 딕셔너리에서 비밀번호를 확인하도록 수정
        if username in users and users[username]["password"] == password:
            session["username"] = username
            flash("로그인 성공!", "success")
            return redirect(url_for('search_location'))
        else:
            flash("사용자 이름 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route("/search", methods=["GET", "POST"])
def search_location():
    if not session.get("username"):
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))

    search_query = request.form.get("query", "").strip()
    
    # 기본 지도 정보 (검색어가 없거나 유효하지 않을 때)
    current_location_info = SEARCH_LOCATIONS.get(search_query, SEARCH_LOCATIONS["서울특별시"])
    
    current_map_image = current_location_info["image"]
    current_map_width = current_location_info["map_width"]
    current_map_height = current_location_info["map_height"]
    
    display_locations_on_map = [] # 지도 위에 표시될 주차장 정보
    display_locations_list = [] # 지도 아래 목록에 표시될 주차장 정보

    for lot_id in current_location_info["lots"]:
        lot_data = LOTS.get(lot_id)
        if lot_data:
            estimated_points_per_hour = calculate_eco_points(lot_id, 0, 60)
            
            # 지도 위에 표시될 정보 (좌표 포함)
            if "map_coords" in lot_data and lot_data["map_coords"] is not None:
                display_locations_on_map.append({
                    "id": lot_id,
                    "name": lot_data["name"],
                    "map_coords": lot_data["map_coords"],
                    "base_price_per_min": lot_data["base_price_per_min"],
                    "estimated_points_per_hour": estimated_points_per_hour
                })
            
            # 목록에 표시될 정보 (모든 주차장)
            display_locations_list.append({
                "id": lot_id,
                "name": lot_data["name"],
                "image": lot_data["image"], # 주차장 도면 이미지
                "base_price_per_min": lot_data["base_price_per_min"],
                "estimated_points_per_hour": estimated_points_per_hour
            })
    
    # 검색 결과가 없으면 메시지 표시
    if search_query and not display_locations_list:
        flash(f"'{search_query}'에 해당하는 주차장을 찾을 수 없습니다.<br>예시: 서울특별시, A, B", "error")
        # 이 경우에는 리다이렉트하지 않고 현재 페이지를 다시 렌더링
        return render_template("search_location.html", 
                           search_query=search_query, 
                           current_map_image=current_map_image,
                           current_map_width=current_map_width,
                           current_map_height=current_map_height,
                           display_locations_on_map=display_locations_on_map,
                           display_locations_list=[], # 검색 결과 없음을 명시
                           search_locations=SEARCH_LOCATIONS,
                           LOTS=LOTS)
    
    # 렌더링할 때 필요한 모든 데이터 전달
    return render_template("search_location.html", 
                           search_query=search_query, 
                           current_map_image=current_map_image,
                           current_map_width=current_map_width,
                           current_map_height=current_map_height,
                           display_locations_on_map=display_locations_on_map, # 지도 위에 맵핑될 주차장
                           display_locations_list=display_locations_list, # 목록으로 표시될 주차장
                           search_locations=SEARCH_LOCATIONS, # Jinja2 globals에 이미 등록되어 있지만 명시적으로 전달
                           LOTS=LOTS) # Jinja2 globals에 이미 등록되어 있지만 명시적으로 전달


@app.route("/lots")
def select_lot():
    if not session.get("username"):
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))
    # 여기는 더 이상 사용되지 않으므로, search_location으로 리다이렉트
    return redirect(url_for('search_location'))

@app.route("/lot/<lot_id>")
def lot(lot_id):
    if not session.get("username"):
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))

    lot_info = LOTS.get(lot_id)
    if not lot_info:
        flash("존재하지 않는 주차장입니다.", "error")
        return redirect(url_for('search_location'))

    lot_reservations = reservations.get(lot_id, [])
    current_dt = datetime.now() # datetime 객체 자체를 전달
    now_timestamp = int(current_dt.timestamp()) # 기존 now 변수명과 일관성을 위해 추가

    # 각 주차 공간의 예약 상태와 예상 종료 시간 계산
    spots_data = []
    for spot in lot_info['spots']:
        is_currently_occupied = False
        reserved_info = None

        # Check for current occupancy
        for r in lot_reservations:
            if r['spot'] == spot['id'] and r['start'] <= now_timestamp < r['end']:
                is_currently_occupied = True
                reserved_info = {
                    "user": r['user'],
                    "end_time": datetime.fromtimestamp(r['end']).strftime('%H:%M')
                }
                break

        # Calculate the start of the next 30-minute interval from now
        # This will be the first 30-minute block boundary that is *after* current_dt
        next_30min_interval_start_dt = current_dt.replace(second=0, microsecond=0)
        if next_30min_interval_start_dt.minute > 30:
            next_30min_interval_start_dt = next_30min_interval_start_dt.replace(hour=next_30min_interval_start_dt.hour + 1, minute=0)
        elif next_30min_interval_start_dt.minute > 0:
            next_30min_interval_start_dt = next_30min_interval_start_dt.replace(minute=30)
        
        next_30min_interval_start_ts = int(next_30min_interval_start_dt.timestamp())
        next_30min_interval_end_ts = int((next_30min_interval_start_dt + timedelta(minutes=30)).timestamp())

        is_next_slot_occupied = False
        # Check if the *next* 30-minute slot is occupied
        for r in lot_reservations:
            if r['spot'] == spot['id'] and not (next_30min_interval_end_ts <= r['start'] or next_30min_interval_start_ts >= r['end']):
                is_next_slot_occupied = True
                break
        
        # Determine the display status for the spot area button
        # Red if currently occupied OR the next 30-min slot is occupied
        display_status_class = 'spot-available-now' # Default to green
        if is_currently_occupied or is_next_slot_occupied:
            display_status_class = 'spot-unavailable' # Red if currently occupied OR next slot is occupied
        
        # --- DEBUG PRINT ---
        print(f"Spot {spot['id']}: current_dt={current_dt.strftime('%H:%M')}, "
              f"next_30min_interval_start_dt={next_30min_interval_start_dt.strftime('%H:%M')}, "
              f"is_currently_occupied={is_currently_occupied}, "
              f"is_next_slot_occupied={is_next_slot_occupied}, "
              f"final_display_class={display_status_class}")
        # --- END DEBUG PRINT ---

        spots_data.append({
            "id": spot['id'],
            "coords": spot['coords'],
            "status": "occupied" if is_currently_occupied else "available", # Keep original status for timeline logic
            "display_class": display_status_class, # New field for initial color
            "reserved_info": reserved_info,
            "spot_density": spot['spot_density']
        })

    return render_template("lot.html", lot=lot_info, lot_id=lot_id, spots_data=spots_data, now=now_timestamp, current_dt=current_dt) # current_dt 전달


@app.route("/reservation_status/<lot_id>/<int:spot_id>")
def reservation_status(lot_id, spot_id):
    now_dt = datetime.now()
    today_start_ts = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    today_end_ts = int(now_dt.replace(hour=23, minute=59, second=59, microsecond=999999).timestamp())

    lot_revs = reservations.get(lot_id, [])
    
    # Filter reservations for the current spot and today
    spot_reservations_today = [
        r for r in lot_revs 
        if r['spot'] == spot_id and 
           r['start'] <= today_end_ts and r['end'] >= today_start_ts
    ]

    # Calculate next available 30-minute start time
    next_available_start_time = None
    
    # Round current time up to the nearest 30-minute interval
    current_time_rounded = now_dt.replace(second=0, microsecond=0)
    if current_time_rounded.minute > 30:
        current_time_rounded = current_time_rounded.replace(hour=current_time_rounded.hour + 1, minute=0)
    elif current_time_rounded.minute > 0:
        current_time_rounded = current_time_rounded.replace(minute=30)

    # Check slots from current_time_rounded until end of day
    slot_time = current_time_rounded
    while slot_time.date() == now_dt.date(): # Check only for today
        slot_start_ts = int(slot_time.timestamp())
        slot_end_ts = int((slot_time + timedelta(minutes=30)).timestamp())
        
        is_slot_occupied = False
        for r in spot_reservations_today:
            # Check for overlap: (start1 < end2 AND end1 > start2)
            if not (slot_end_ts <= r['start'] or slot_start_ts >= r['end']):
                is_slot_occupied = True
                break
        
        if is_slot_occupied: # If this slot is occupied, move to the next
            slot_time += timedelta(minutes=30)
        else: # This slot is available
            next_available_start_time = slot_time
            break # Found the first available slot

    return jsonify({
        'reserved': any(r['spot'] == spot_id and r['start'] <= int(now_dt.timestamp()) < r['end'] for r in lot_revs), # Is currently occupied
        'next_available_start_time': next_available_start_time.strftime('%H:%M') if next_available_start_time else None,
        'reservations': [
            {'start': r['start'], 'end': r['end'], 'user': r['user']} 
            for r in spot_reservations_today # Return all relevant reservations for timeline
        ]
    })


@app.route("/reserve/<lot_id>/<int:spot_id>", methods=["POST"])
def reserve(lot_id, spot_id):
    username = session.get("username")
    if not username:
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))

    # 사용자 정보가 users 딕셔너리에 없으면 초기화
    if username not in users:
        users[username] = {"points": 0}

    # 기존 예약 페이지는 사용하지 않고, lot.html에서 바로 예약 정보를 받음
    date_str = request.form.get("date")
    hour = int(request.form.get("hour"))
    minute = int(request.form.get("minute"))
    duration_min = int(request.form.get("duration_min"))

    try:
        start_dt = datetime.strptime(f"{date_str} {hour}:{minute}", "%Y-%m-%d %H:%M")
    except Exception:
        flash("잘못된 날짜 또는 시간 형식입니다.", "error")
        return redirect(url_for('lot', lot_id=lot_id))

    start_ts = int(start_dt.timestamp())
    end_ts = int((start_dt + timedelta(minutes=duration_min)).timestamp())

    # 현재 시간보다 이전 시간을 예약하려고 하는 경우 방지
    if start_ts < int(datetime.now().timestamp()):
        flash("현재 시간보다 이전 시간은 예약할 수 없습니다.", "error")
        return redirect(url_for('lot', lot_id=lot_id))

    overlap = check_overlapping(username, lot_id, spot_id, start_ts, end_ts)
    if overlap == True:
        flash("동일 시간대에 이미 예약이 있습니다.", "error")
        return redirect(url_for('lot', lot_id=lot_id))
    elif overlap == "spot_taken":
        flash("선택하신 공간은 이미 다른 사용자에게 예약 중입니다.", "error")
        return redirect(url_for('lot', lot_id=lot_id))

    lot_info = LOTS.get(lot_id)
    base_price_per_min = lot_info['base_price_per_min']
    price = duration_min * base_price_per_min

    # 친환경 포인트 계산
    points_earned = calculate_eco_points(lot_id, spot_id, duration_min)

    session['pending_reservation'] = {
        'lot_id': lot_id,
        'spot': spot_id,
        'start': start_ts,
        'end': end_ts,
        'user': username,
        'price': price,
        'points_earned': points_earned
    }
    return render_template("payment.html", price=price, points_earned=points_earned, user_points=users[username]["points"])


@app.route("/payment/confirm", methods=["POST"])
def payment_confirm():
    pending = session.pop('pending_reservation', None)
    if not pending:
        flash("결제 정보가 만료되었거나 올바르지 않습니다.", "error")
        return redirect(url_for('search_location'))

    lot_id = pending['lot_id']
    spot_id = pending['spot']
    start = pending['start']
    end = pending['end']
    user = pending['user']
    price = pending['price']
    points_earned = pending['points_earned']
    points_to_use = int(request.form.get("points_to_use", 0))

    # 포인트 사용 로직
    actual_price = price
    if points_to_use > 0:
        username = session.get("username")
        if username and users[username]["points"] >= points_to_use:
            actual_price = max(0, price - points_to_use)
            users[username]["points"] -= points_to_use
        else:
            flash("보유 포인트가 부족합니다.", "error")
            return redirect(url_for('lot', lot_id=lot_id))

    if lot_id not in reservations:
        reservations[lot_id] = []

    # 최종적으로 다시 한번 예약 가능 여부 확인 (동시성 문제 방지)
    for r in reservations[lot_id]:
        if r['spot'] == spot_id and not (end <= r['start'] or start >= r['end']):
            flash("예약하려는 자리가 이미 예약되어 있습니다.", "error")
            return redirect(url_for('lot', lot_id=lot_id))

    reservations[lot_id].append({
        "id": int(datetime.now().timestamp() * 1000), # 고유 ID 생성
        "user": user,
        "spot": spot_id,
        "start": start,
        "end": end,
        "original_price": price, # 원래 가격
        "actual_price": actual_price, # 실제로 지불한 가격
        "points_earned": points_earned, # 적립 포인트
        "status": "paid" # 예약 상태 추가
    })
    
    # 포인트 적립
    if user in users:
        users[user]["points"] += points_earned

    flash(f"결제가 완료되었습니다! 예약이 확정되었습니다.<br>적립된 포인트: {points_earned}점<br>현재 보유 포인트: {users[user]['points']}점", "success")
    return redirect(url_for('lot', lot_id=lot_id))

@app.route("/my/reservations")
def my_reservations():
    username = session.get("username")
    if not username:
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))

    # 사용자 정보가 users 딕셔너리에 없으면 초기화
    if username not in users:
        users[username] = {"points": 0}

    mylist = []
    for lot_id, revs in reservations.items():
        for r in revs:
            if r['user'] == username:
                mylist.append({**r, "lot_id": lot_id})
    return render_template("my_reservations.html", reservations=mylist, current_points=users[username]["points"])

@app.route("/cancel_reservation/<lot_id>/<res_id>")
def cancel_reservation(lot_id, res_id):
    if 'username' not in session:
        flash("로그인 후 이용해주세요.", "error")
        return redirect(url_for('login'))

    username = session['username']
    lot_revs = reservations.get(lot_id, [])
    
    # string 형태의 res_id를 int로 변환
    try:
        res_id = int(res_id)
    except (ValueError, TypeError):
        return show_message_modal("유효하지 않은 예약 ID입니다.", url_for('my_reservations'))

    reservation_to_cancel = next((r for r in lot_revs if r['id'] == res_id), None)
    
    if reservation_to_cancel and reservation_to_cancel['user'] == username:
        # 예약 삭제 (간단한 구현)
        reservations[lot_id].remove(reservation_to_cancel)
        
        # 포인트 회수 (결제가 완료된 경우만)
        if reservation_to_cancel.get('status') == 'paid':
            cancelled_points_earned = reservation_to_cancel['points_earned']
            users[username]['points'] = max(0, users[username]['points'] - cancelled_points_earned)
            return show_message_modal(f"예약이 취소되었습니다.<br>적립된 포인트 {cancelled_points_earned}점이 회수되었습니다.", url_for('my_reservations'))
        else:
            return show_message_modal("예약이 취소되었습니다.", url_for('my_reservations'))
    else:
        return show_message_modal("예약 정보를 찾을 수 없거나 권한이 없습니다.", url_for('my_reservations'))
        
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# 메시지 모달을 표시하는 헬퍼 함수
def show_message_modal(message, redirect_url):
    return render_template("_message_modal.html", message=message, redirect_url=redirect_url)

# calculate_eco_points 함수를 Jinja2 템플릿에서 직접 사용할 수 있도록 등록
app.jinja_env.globals['calculate_eco_points'] = calculate_eco_points
# SEARCH_LOCATIONS와 LOTS도 Jinja2 템플릿에서 직접 사용할 수 있도록 등록
app.jinja_env.globals['SEARCH_LOCATIONS'] = SEARCH_LOCATIONS
app.jinja_env.globals['LOTS'] = LOTS

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")