import json
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import re

from wsproto.frame_protocol import NULL_MASK

# ✅ 위도/경도 함수
geolocator = Nominatim(user_agent="location_finder")

def clean_address(address):
    if '대한민국' in address:
        address = address.split('대한민국')[0].strip() + ' 대한민국'
    parts = list(dict.fromkeys(address.split(',')))
    cleaned = ', '.join(p.strip() for p in parts if p.strip())
    return cleaned

def get_lat_lng(address, retries=3):
    cleaned = clean_address(address)
    for i in range(retries):
        try:
            location = geolocator.geocode(cleaned, timeout=5)
            if location:
                return location.latitude, location.longitude
            return None, None
        except (GeocoderTimedOut, GeocoderUnavailable):
            print(f"⚠️ 위치 조회 실패, 재시도 중... ({i + 1}/{retries})")
            time.sleep(1)
    return None, None


# ✅ 드라이버 설정
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# ✅ 테스트용 호텔 링크 불러오기 (5개만)
print("▶️ JSON 호텔 링크 파일 불러오기")
with open("agoda_links_hayeong.json", "r", encoding="utf-8") as f:
    hotel_links = json.load(f)[:5]

result = []

def crawl_sample_hotel(link):
    print(f"\n호텔 추적 시작: {link}")
    driver.get(link)
    time.sleep(3)
    hotel_info = {}
    hotel_info["detail_page_url"] = link

    try:
        hotel_info["hotel_name"] = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1[data-selenium="hotel-header-name"]'))).text
    except:
        hotel_info["hotel_name"] = None

    try:
        address = driver.find_element(By.CSS_SELECTOR, '[data-selenium="hotel-address-map"]').text
    except:
        address = None
    hotel_info["address"] = address

    lat, lng = get_lat_lng(address)
    print(f"▪️ 위치: {lat}, {lng}")
    hotel_info["latitude"] = lat
    hotel_info["longitude"] = lng

    try:
        price = driver.find_element(By.CSS_SELECTOR, '[data-element-name="final-price"]').text.replace("\n", "").strip()
    except:
        price = None
    hotel_info["price"] = price

    try:
        rating_candidates = driver.find_elements(By.XPATH, '//p[contains(@class, "Typographystyled__TypographyStyled-sc-j18mtu-0")]')
        for el in rating_candidates:
            text = el.text.strip()
            if re.match(r'^\d+(\.\d+)?$', text):
                hotel_info["avg_rating"] = text
                break
    except:
        hotel_info["avg_rating"] = None

    # ✅ 리뷰 수집 (10개만)
    reviews_list = []
    page = 1
    while True:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.Review-comment')))
            reviews = driver.find_elements(By.CSS_SELECTOR, 'div.Review-comment')
            print(f"  - {len(reviews)}개 리뷰 페이지 {page}")
            for review in reviews:
                try:
                    review_data = {
                        "reviewer": "",
                        "rating": "",
                        "title": "",
                        "content": "",
                        "reviewer_country": "",
                        "reviewer_type": "",
                    }
                    try:
                        # review는 해당 리뷰 블록 요소
                        spans = review.find_elements(By.XPATH, './/span')
                        review_data["rating"] = None
                        for span in spans:
                            txt = span.text.strip()
                            if review_data["rating"] is None and re.match(r'^\d+(\.\d+)?$', txt):  # 숫자만
                                review_data["rating"] = txt
                            if review_data["rating"]:
                                break
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
                        reviewer_text = review.find_element(By.CSS_SELECTOR, '[data-info-type="reviewer-name"]').text.strip()
                        nickname, country = (reviewer_text.split("(")[0].strip(), reviewer_text.split("(")[1].replace(")", "").strip()) if "(" in reviewer_text else (reviewer_text, "정보 없음")
                        review_data["reviewer"] = nickname
                        review_data["reviewer_country"] = country
                    except:
                        review_data["reviewer"] = None
                        review_data["reviewer_country"] = None
                    try:
                        review_data["reviewer_type"] = review.find_element(By.CSS_SELECTOR, '[data-info-type="group-name"]').text
                    except:
                        review_data["reviewer_type"] = None
                    reviews_list.append(review_data)
                    if len(reviews_list) >= 10:
                        break
                except:
                    continue
            if len(reviews_list) >= 10:
                break
            next_btn = driver.find_elements(By.XPATH, f'//button[@aria-label="이용후기 페이지로 이동하기 {page + 1}"]')
            if next_btn:
                driver.execute_script("arguments[0].click();", next_btn[0])
                time.sleep(2)
                page += 1
            else:
                break
        except:
            break

    print(f"  ✔️ 수집 리뷰: {len(reviews_list)}개")
    hotel_info["review_count"] = len(reviews_list)
    hotel_info["reviews"] = reviews_list
    return hotel_info

# ✅ 호텔별 리뷰 수집
for url in hotel_links:
    data = crawl_sample_hotel(url)
    result.append(data)

# 저장
with open("agoda_test_sample_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("\n🚀 수집 완료! 결과는 agoda_test_sample_result.json에 저장되어있습니다.")
driver.quit()
