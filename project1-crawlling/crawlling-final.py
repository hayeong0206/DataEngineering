import json
import time
import os
import re
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# ✅ MongoDB 연결
mongo_uri = "mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["dataEngineering"]
collection = db["Agoda_jeju"]

# ✅ 드라이버 설정
options = Options()
#options.add_argument("--headless=new")  # ✅ 새 방식의 headless 모드
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")  # 가상 브라우저 창 크기
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# ✅ 기존에 저장된 호텔 링크 불러오기 (중단 지점부터 시작 가능하도록)
visited_links_file = "visited_hotel_links.json"
if os.path.exists(visited_links_file):
    with open(visited_links_file, "r", encoding="utf-8") as f:
        visited_links = set(json.load(f))
else:
    visited_links = set()

# ✅ 전체 호텔 데이터 저장 리스트
all_hotels = []

# ✅ 위도/경도 함수
geolocator = Nominatim(user_agent="location_finder")

def clean_address(address):
    if not address:
        return None
    if '대한민국' in address:
        address = address.split('대한민국')[0].strip() + ' 대한민국'
    parts = list(dict.fromkeys(address.split(',')))
    return ', '.join(p.strip() for p in parts if p.strip())

def get_lat_lng(address, retries=3):
    if not address:
        return None, None
    cleaned = clean_address(address)
    for i in range(retries):
        try:
            location = geolocator.geocode(cleaned, timeout=5)
            if location:
                return location.latitude, location.longitude
        except (GeocoderTimedOut, GeocoderUnavailable):
            print(f"⚠️ 위치 조회 실패, 재시도 중... ({i + 1}/{retries})")
            time.sleep(1)
    return None, None

# ✅ 호텔 링크 불러오기
with open("agoda_links_hayeong.json", "r", encoding="utf-8") as f:
    hotel_links = json.load(f)

# ✅ 크롤링 함수 정의
def crawl_sample_hotel(link):
    print(f"\n호텔 추적 시작: {link}")
    driver.get(link)
    time.sleep(3)
    hotel_info = {"detail_page_url": link}

    try:
        hotel_name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1[data-selenium="hotel-header-name"]'))).text
    except:
        hotel_name = None

    hotel_info["hotel_name"] = hotel_name
    print(f"🏨 호텔 이름: {hotel_name}")

    try:
        address = driver.find_element(By.CSS_SELECTOR, '[data-selenium="hotel-address-map"]').text
    except:
        address = None
    hotel_info["address"] = address

    lat, lng = get_lat_lng(address)
    hotel_info["latitude"] = lat
    hotel_info["longitude"] = lng

    try:
        price = driver.find_element(By.CSS_SELECTOR, '[data-element-name="final-price"]').text.replace("\n", "").strip()
    except:
        price = None

    hotel_info["price"] = price

    print(f"💰 가격: {hotel_info['price']}")

    try:
        avg_rating_elem = driver.find_element(
            By.XPATH,
            '//div[@data-element-name="review-plate"]//h2//span[1]'
        )
        avg_rating = avg_rating_elem.text.strip()
        if re.match(r'^\d+(\.\d+)?$', avg_rating):
            hotel_info["avg_rating"] = avg_rating
        else:
            hotel_info["avg_rating"] = None
    except:
        hotel_info["avg_rating"] = None

    # ✅ 실제 리뷰 수 텍스트에서 숫자만 추출하여 저장
    try:
        review_text = driver.find_element(By.CSS_SELECTOR,
                                          'p.Typographystyled__TypographyStyled-sc-j18mtu-0.Hkrzy.kite-js-Typography').text
        match = re.search(r'(\d+)', review_text)
        review_count_from_text = int(match.group(1)) if match else 0
    except:
        review_count_from_text = 0

    hotel_info["review_count"] = review_count_from_text

    print(f"📍 주소: {hotel_info['address']}")
    print(f"📍 위치: {hotel_info['latitude']}, {hotel_info['longitude']}")
    print(f"⭐ 평점: {hotel_info['avg_rating']}")
    print(f"⭐ 리뷰 개수: {hotel_info['review_count']}")

    reviews_list = []
    page = 1
    while True:
        try:
            reviews = driver.find_elements(By.CSS_SELECTOR, 'div.Review-comment')
            if not reviews:
                print("📭 리뷰 없음.")
                break

            page_review_count = 0
            for review in reviews:
                review_data = {}
                try:
                    # 평점은 여러 구조로 올 수 있어, span > 정규식 숫자 필터 방식 유지 + 추가 XPath 고려
                    rating_found = None

                    # 1차 시도: span 중 숫자 텍스트 찾기
                    spans = review.find_elements(By.XPATH, './/span')
                    for span in spans:
                        txt = span.text.strip()
                        if re.match(r'^\d+(\.\d+)?$', txt):
                            rating_found = txt
                            break

                    # 2차 시도: 클래스 기반
                    if not rating_found:
                        try:
                            rating_found = review.find_element(By.CLASS_NAME, 'Review-comment-leftScore').text.strip()
                        except:
                            pass

                    review_data["rating"] = rating_found if rating_found else None

                except:
                    review_data["rating"] = None

                try:
                    review_data["title"] = review.find_element(By.CSS_SELECTOR, '[data-testid="review-title"]').text
                except:
                    review_data["title"] = None
                try:
                    review_data["content"] = review.find_element(By.CSS_SELECTOR, '[data-testid="review-comment"]').text
                except:
                    review_data["content"] = None
                try:
                    text = review.find_element(By.CSS_SELECTOR, '[data-info-type="reviewer-name"]').text.strip()
                    name, country = (text.split("(")[0].strip(), text.split("(")[1].replace(")", "").strip()) if "(" in text else (text, "정보 없음")
                    review_data["reviewer"] = name
                    review_data["reviewer_country"] = country
                except:
                    review_data["reviewer"] = None
                    review_data["reviewer_country"] = None
                try:
                    review_data["reviewer_type"] = review.find_element(By.CSS_SELECTOR, '[data-info-type="group-name"]').text
                except:
                    review_data["reviewer_type"] = None
                reviews_list.append(review_data)
                if page_review_count == 0:
                    print(
                        f"📝 첫 리뷰 (p.{page}): {review_data.get('reviewer')} | 평점: {review_data.get('rating')} | {review_data.get('title')}")
                page_review_count += 1

            next_btn = driver.find_elements(By.XPATH, f'//button[@aria-label="이용후기 페이지로 이동하기 {page + 1}"]')
            if next_btn:
                driver.execute_script("arguments[0].scrollIntoView(true);", next_btn[0])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_btn[0])
                time.sleep(3)
                page += 1
            else:
                print("⛔️ 다음 페이지 없음. 리뷰 수집 종료")
                break
        except Exception as e:
            print("❗ 리뷰 수집 중 예외 발생:", e)
            break

    # ✅ 리뷰 최대 갯수 수집 후 저장
    hotel_info["reviews"] = reviews_list
    all_hotels.append(hotel_info)
    collection.insert_one(hotel_info)
    visited_links.add(link)
    with open(visited_links_file, "w", encoding="utf-8") as f:
        json.dump(list(visited_links), f, ensure_ascii=False, indent=2)
    print(f"✅ MongoDB 및 visited_links 저장 완료: {hotel_name} (리뷰 {len(reviews_list)}건)")

    return hotel_info



# ✅ 수집 실행
for url in hotel_links:
    if url in visited_links:
        print(f"⏩ 이미 수집된 링크입니다. 건너뜁니다: {url}")
        continue  # 이미 수집한 링크는 건너뜀
    data = crawl_sample_hotel(url)

# ✅ 수집 데이터 json으로 저장
all_data = list(collection.find({}, {"_id": 0}))
with open("../project1/agoda_hotel_details.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print("\n✅ 모든 수집 및 저장 완료")
driver.quit()
