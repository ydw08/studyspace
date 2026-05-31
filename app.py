import streamlit as st
import pandas as pd
import requests
import math
import os
import json
import re  # AI 대답에서 숫자만 강제로 추출하는 모듈
from streamlit_geolocation import streamlit_geolocation

# ==========================================
# ⚙️ 기본 설정 및 API 키
# ==========================================
st.set_page_config(page_title="학생을 위한 추천 공부장소", page_icon="📝", layout="centered")

KAKAO_API_KEY = "17c2755ebd29e0cd5c6cd7b52d59f105"
# 🌟 요청하신 대로 API 키 자리를 빈 공간으로 비워두었습니다.
GEMINI_API_KEY = "AIzaSyAsO4FSthGy-fmS6bVha5w9cBzKJQ1IFmg"  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HAGWON_CSV = os.path.join(BASE_DIR, "학원교습소정보_2026년04월30일기준.zip")
LIB_CSV = os.path.join(BASE_DIR, "전국도서관표준데이터.csv")
FEEDBACK_DB = os.path.join(BASE_DIR, "feedback_scores.json")  # 📂 실시간 피드백 누적 DB 파일

# ==========================================
# 📂 실시간 피드백 데이터베이스(JSON) 관리 함수
# ==========================================
def load_feedback_scores():
    """DB 파일에서 장소별 누적 피드백 점수를 불러옵니다."""
    if os.path.exists(FEEDBACK_DB):
        try:
            with open(FEEDBACK_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_feedback_score(place_name, score_change):
    """사용자 리뷰로 인한 점수 변동을 DB에 누적하여 저장합니다."""
    scores = load_feedback_scores()
    scores[place_name] = scores.get(place_name, 0) + score_change
    with open(FEEDBACK_DB, 'w', encoding='utf-8') as f:
        json.dump(scores, f, ensure_ascii=False, indent=4)

# ==========================================
# 🤖 Gemini AI 자연어 처리(NLP) 분석 함수 (클린 버전)
# ==========================================
def analyze_review_with_gemini(review_text):
    """Gemini API를 사용하여 사용자의 한줄평이 긍정적(조용함)인지 부정적(시끄러움)인지 분석합니다."""
    if not GEMINI_API_KEY:
        return 0
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    사용자가 공부 장소를 이용하고 남긴 한줄평을 분석해서 학습 환경 점수 조정값을 전수해줘.
    - 너무 시끄럽거나 가기 불편하다는 부정적인 내용이면: -10에서 -1 사이의 정수 (심할수록 낮은 숫자)
    - 생각보다 조용하고 공부하기 좋았다는 긍정적인 내용이면: 1에서 10 사이의 정수 (좋을수록 높은 숫자)
    - 평범하거나 소음과 관계없는 내용이면: 0
    
    ⚠️ 규칙: 다른 설명은 절대 하지 말고 오직 '정수 숫자 하나'만 반환해줘.
    
    사용자 리뷰: "{review_text}"
    """
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            ai_response = res.json()['contents'][0]['parts'][0]['text'].strip()
            numbers = re.findall(r'-?\d+', ai_response)
            if numbers:
                return int(numbers[0])
    except:
        pass
        
    return 0  # 에러 발생 시 화면 표시 없이 조용히 0점 반환

# ==========================================
# 🛠️ 핵심 데이터 처리 함수
# ==========================================

def get_lat_lon_by_keyword(keyword):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        res = requests.get(url, headers=headers, params={"query": keyword, "size": 1})
        if res.status_code == 200:
            docs = res.json().get('documents')
            if docs:
                y = float(docs[0]['y'])
                x = float(docs[0]['x'])
                address = docs[0].get('road_address_name') or docs[0].get('address_name')
                region = address.split()[1] if address else ""
                exact_name = docs[0]['place_name']
                return y, x, region, exact_name
    except:
        pass
    return None, None, None, None

def get_region_by_coords(lat, lon):
    url = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"x": lon, "y": lat}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            for doc in res.json().get('documents', []):
                if doc['region_type'] == 'H': 
                    return doc['region_2depth_name']
    except:
        pass
    return ""

def search_places(lat, lon, keyword, radius=3000):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": keyword, "y": lat, "x": lon, "radius": radius, "size": 15}
    places = []
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            for p in res.json().get('documents', []):
                places.append({
                    "장소명": p['place_name'],
                    "주소": p['road_address_name'] or p['address_name'],
                    "위도": float(p['y']),
                    "경도": float(p['x']),
                    "종류": keyword
                })
    except:
        pass
    return places

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

@st.cache_data
def load_csv_data(file_name):
    try:
        return pd.read_csv(file_name, encoding='utf-8')
    except:
        return pd.read_csv(file_name, encoding='cp949')

# ==========================================
# 🖥️ 프론트엔드 (웹 사이트 화면)
# ==========================================

st.title("🎯 학생을 위한 추천 공부장소")
st.caption("StudySpace AI: 방과 후, 내 주변의 숨겨진 아지트 찾기 프로젝트")
st.write("---")

st.header("🧠 STEP 1. 나의 학습 성향 테스트")
noise_pref = st.radio(
    "Q1. 공부할 때 선호하는 분위기는 어떤가요?",
    ("완벽한 무소음 (숨소리도 안 들리는 밀폐형)", 
     "적당한 백색소음 (책 넘기는 소리나 잔잔한 음악이 있는 오픈형)", 
     "자유로운 대화 필요 (말하면서 암기하거나 타이핑하는 토론형)")
)

st.header("📍 STEP 2. 출발지 설정")
st.write("평일 방과 후라면 학교를, 주말이라면 현재 위치를 선택해 주세요.")

search_method = st.radio(
    "탐색 기준을 선택하세요.",
    ("🏫 학교 이름으로 찾기", "📍 내 현재 위치로 찾기 (GPS)"),
    horizontal=True
)

search_type = ""
school_name = ""
location = None

if search_method == "🏫 학교 이름으로 찾기":
    search_type = "school"
    school_name = st.text_input("다니고 있는 학교 이름을 입력하세요.", placeholder="예: 순천고등학교, 금당고등학교")
else:
    search_type = "gps"
    st.info("👇 아래의 **[Get Location]** 글씨(또는 과녁 아이콘)를 먼저 클릭해서 위치를 불러와주세요!")
    location = streamlit_geolocation()

st.write("---")

# 실시간 피드백 점수 미리 로드
feedback_scores = load_feedback_scores()

if st.button("✨ 나에게 맞는 공부방 TOP 10 찾기", type="primary"):
    user_lat, user_lon, region, exact_target = None, None, None, None
    
    if search_type == "school" and school_name:
        user_lat, user_lon, region, exact_target = get_lat_lon_by_keyword(school_name)
    elif search_type == "gps":
        if location and location['latitude'] is not None and location['longitude'] is not None:
            user_lat = location['latitude']
            user_lon = location['longitude']
            region = get_region_by_coords(user_lat, user_lon)
            exact_target = "현재 위치"
        else:
            st.error("위의 [Get Location]을 눌러 GPS 위치 권한을 먼저 승인해 주세요.")
            
    if not user_lat:
        st.error("학교 이름을 정확히 입력하거나 위치 권한을 승인해 주세요.")
    else:
        with st.spinner("주변의 안전한 교육 시설과 맞춤형 공간을 탐색 중입니다... 🔍"):
            st.success(f"성향 분석 완료! 기준점 **[{exact_target}]** 주변의 최적 공간을 매칭했습니다.")
            
            public_places = []
            
            # --- 공공데이터 1: 교육청 인증 독서실 ---
            df_hagwon = load_csv_data(HAGWON_CSV)
            df_dokseo = df_hagwon[
                (df_hagwon['학원명'].astype(str).str.contains('독서실', na=False) | 
                 df_hagwon['교습과정명'].astype(str).str.contains('독서실', na=False)) & 
                (df_hagwon['도로명주소'].astype(str).str.contains(region, na=False))
            ]
            for _, row in df_dokseo.head(10).iterrows():
                p_lat, p_lon, _, _ = get_lat_lon_by_keyword(row['도로명주소'])
                if p_lat:
                    public_places.append({
                        "장소명": row['학원명'], "주소": row['도로명주소'],
                        "위도": p_lat, "경도": p_lon, "종류": "🎖️ 교육청 인증 독서실"
                    })
            
            # --- 공공데이터 2: 전국 공공도서관 ---
            df_lib = load_csv_data(LIB_CSV)
            df_local_lib = df_lib[df_lib['소재지도로명주소'].astype(str).str.contains(region, na=False)]
            for _, row in df_local_lib.iterrows():
                lat_val = row.get('위도')
                lon_val = row.get('경도')
                
                if pd.notna(lat_val) and pd.notna(lon_val):
                    public_places.append({
                        "장소명": row['도서관명'], "주소": row['소재지도로명주소'],
                        "위도": float(lat_val), "경도": float(lon_val), "종류": "📚 무료 공공도서관"
                    })
            
            # --- 민간데이터: 카카오맵 API ---
            private_places = []
            for kw in ["스터디카페", "북카페", "카페"]:
                private_places.extend(search_places(user_lat, user_lon, kw))
            
            # 융합 및 중복 제거
            all_places = public_places + private_places
            unique_places = {p['장소명']: p for p in all_places}.values()
            
            # --- 매칭 알고리즘 채점 ---
            results = []
            for p in unique_places:
                dist = haversine(user_lat, user_lon, p['위도'], p['경도'])
                dist_score = max(0, 50 - (dist * 10)) 
                
                pref_score = 0
                p_type = p['종류']
                
                if "무소음" in noise_pref:
                    if "독서실" in p_type: pref_score = 50
                    elif "도서관" in p_type: pref_score = 30
                    elif "스터디카페" in p_type: pref_score = 20
                    else: pref_score = 10
                elif "백색소음" in noise_pref:
                    if "스터디카페" in p_type or "북카페" in p_type: pref_score = 50
                    elif "도서관" in p_type: pref_score = 40
                    elif "카페" in p_type: pref_score = 30
                    else: pref_score = 10
                else: 
                    if p_type == "카페": pref_score = 50
                    elif "북카페" in p_type: pref_score = 30
                    else: pref_score = 0
                    
                # AI 분석 피드백 가중치 결합 로직
                ai_feedback_bonus = feedback_scores.get(p['장소명'], 0)
                total_score = dist_score + pref_score + ai_feedback_bonus
                
                results.append({
                    "장소명": p['장소명'], "구분": p_type, "주소": p['주소'],
                    "거리(km)": round(dist, 2), "AI 누적 보너스": ai_feedback_bonus, "종합 점수": round(total_score, 1),
                    "위도": p['위도'], "경도": p['경도']
                })
            
            # --- 정렬 및 결과 출력 ---
            results.sort(key=lambda x: x['종합 점수'], reverse=True)
            top_10 = results[:10]
            
            if top_10:
                df_top = pd.DataFrame(top_10)
                st.subheader(f"🗺️ [{exact_target}] 주변 최적의 공부방 위치")
                st.map(df_top, latitude="위도", longitude="경도", size=50)
                
                st.subheader("🏆 나를 위한 맞춤형 공간 TOP 10")
                df_show = df_top.drop(columns=["위도", "경도"])
                df_show.index = range(1, 11) 
                st.dataframe(df_show, use_container_width=True)
                
                st.session_state['current_places'] = [x['장소명'] for x in top_10]
            else:
                st.warning("조건에 맞는 공간이 주변에 없습니다.")

# ==========================================
# 💬 STEP 3. 실시간 한줄평 및 AI 소음도 가중치 반영
# ==========================================
st.write("---")
st.header("💬 STEP 3. 생생 현장 피드백 (AI 실시간 가중치 갱신)")
st.caption("실제 가보니 데이터와 달랐나요? 한줄평을 남기면 AI가 분석하여 장소 점수에 실시간 반영(DB 누적)합니다.")

place_options = st.session_state.get('current_places', ["OO도서관"])

feedback_place = st.selectbox("리뷰를 남길 장소를 선택하세요.", place_options)
user_review = st.text_input("공부방의 실시간 상태를 적어주세요.", placeholder="예: 오늘따라 중학생들이 단체로 와서 좀 시끄러워요 / 생각보다 엄청 조용하고 몰입 잘 됨!")

if st.button("🚀 AI 분석 후 피드백 반영하기"):
    if user_review:
        with st.spinner("Gemini AI가 한줄평의 감성 및 소음도를 분석 중입니다... 🤖"):
            score_change = analyze_review_with_gemini(user_review)
            
            if score_change < 0:
                st.warning(f"🚨 AI 분석 결과: 부정적 피드백 확인 (소음 가중치 {score_change}점 차감 반영 완료)")
            elif score_change > 0:
                st.success(f"✨ AI 분석 결과: 긍정적 피드백 확인 (추천 가중치 +{score_change}점 가산 반영 완료)")
            else:
                st.info("🤔 AI 분석 결과: 일반적인 내용 혹은 보합 데이터 (점수 변동 없음)")
                
            save_feedback_score(feedback_place, score_change)
            st.balloons()
            st.info("🔄 데이터베이스가 성공적으로 업데이트되었습니다! '✨ 나에게 맞는 공부방 TOP 10 찾기' 버튼을 한 번 더 누르시면 변경된 점수가 표에 반영됩니다.")
    else:
        st.error("리뷰 내용을 입력해 주세요.")