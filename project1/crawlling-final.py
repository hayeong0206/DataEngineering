from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import re
from pymongo import MongoClient
from bson import json_util
import os

# ✅ MongoDB 연결 설정
mongo_uri = "mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["dataEngineering"]
collection = db["Agoda_jeju"]

# ✅ 브라우저 설정
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# ✅ 아고다 호텔 목록 페이지
driver.get("https://www.agoda.com/ko-kr/search?city=16901&locale=ko-kr&ckuid=bce345d4-11c0-44e3-a934-169aed514712&prid=0&gclid=CjwKCAjw-qi_BhBxEiwAkxvbkCTF2DP7VFo6gZYForoSvp6VQTbxntzXWu17_d4AyZGMNc-9Ow5mZBoCbAIQAvD_BwE&currency=KRW&correlationId=7f8cf411-6191-4f16-bcd4-7a12782410d4&analyticsSessionId=867935281769294894&pageTypeId=103&realLanguageId=9&languageId=9&origin=KR&stateCode=11&cid=1922887&tag=f7739694-dbb7-41bd-aa27-be7c942ce354&userId=bce345d4-11c0-44e3-a934-169aed514712&whitelabelid=1&loginLvl=0&storefrontId=3&currencyId=26&currencyCode=KRW&htmlLanguage=ko-kr&cultureInfoName=ko-kr&machineName=hk-pc-2f-acm-web-user-5f4654cbb5-rw7rf&trafficGroupId=5&trafficSubGroupId=122&aid=82361&useFullPageLogin=true&cttp=4&isRealUser=true&mode=production&browserFamily=Chrome&cdnDomain=agoda.net&checkIn=2025-04-29&checkOut=2025-04-30&rooms=1&adults=2&children=0&priceCur=KRW&los=1&textToSearch=%EC%A0%9C%EC%A3%BC&productType=-1&travellerType=1&familyMode=off&ds=p3sKdqWiWHJ07bOt")



# ✅ 기존에 저장된 호텔 링크 불러오기 (중단 지점부터 시작 가능하도록)
visited_links_file = "visited_hotel_links.json"
if os.path.exists(visited_links_file):
    with open(visited_links_file, "r", encoding="utf-8") as f:
        visited_links = set(json.load(f))
else:
    visited_links = set()

# ✅ 전체 호텔 링크 저장 파일 불러오기
all_links_file = "all_hotel_links.json"
if os.path.exists(all_links_file):
    with open(all_links_file, "r", encoding="utf-8") as f:
        hotel_links = json.load(f)
    print(f"📂 이전에 저장된 호텔 링크 {len(hotel_links)}개 불러옴")
else:
    hotel_links = set(visited_links)

scroll_pause = 2.5
same_count = 0
max_same = 3
last_height = 0

print("🚀 스크롤 시작")

# ✅ 전체 호텔 데이터 저장 리스트
all_hotels = []

# ✅ 호텔 링크 수집 함수
def extract_hotel_links():
    links = set()
    hotel_elements = driver.find_elements(By.CSS_SELECTOR, 'a[data-testid="property-name-link"]')
    if hotel_elements:
        print("✅ 구조 감지: a[data-testid='property-name-link'] 사용")
    else:
        hotel_elements = driver.find_elements(By.CSS_SELECTOR, 'a[data-selenium="hotel-name"]')
        if hotel_elements:
            print("✅ 구조 감지: a[data-selenium='hotel-name'] 사용")
        else:
            print("❌ 호텔 링크 요소를 찾지 못했습니다.")
            return links

    for el in hotel_elements:
        link = el.get_attribute("href")
        if link and "hotel" in link:
            full_link = "https://www.agoda.com" + link if link.startswith("/") else link
            links.add(full_link)
    return links

## ✅ 수집할 필요가 있을 때만 아래 스크롤 수집 루프 실행
if len(hotel_links) < 110:
    print("🚀 스크롤 및 호텔 링크 수집 시작")

    # ✅ 스크롤 + 링크 수집 루프
    while True:
        try:
            more_button = driver.find_element(By.CSS_SELECTOR, 'button[data-selenium="load-more-button"]')
            if more_button.is_displayed():
                print("➡️ '더 보기' 버튼 클릭")
                driver.execute_script("arguments[0].click();", more_button)
                time.sleep(3)
        except:
            pass

        current_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(last_height, current_height, 300):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(1.2)
        last_height = current_height

        new_links = extract_hotel_links()
        new_only = new_links - hotel_links
        before = len(hotel_links)

        for link in new_only:
            hotel_links.add(link)
            if len(hotel_links) >= 110:
                print("✅ 호텔 100개 수집 완료. 중단합니다.")
                break

        after = len(hotel_links)
        print(f"🔎 현재 누적 수집 호텔 수: {after}")

        if len(hotel_links) >= 110:
            break

        if after == before:
            same_count += 1
            if same_count >= max_same:
                print("✅ 더 이상 로딩되지 않음. 종료.")
                break
        else:
            same_count = 0

    print(f"\n🏨 최종 수집된 호텔 링크 수: {len(hotel_links)}")

    # ✅ 전체 호텔 링크 저장
    with open(all_links_file, "w", encoding="utf-8") as f:
        json.dump(list(hotel_links), f, ensure_ascii=False, indent=2)
    print(f"💾 전체 호텔 링크가 '{all_links_file}' 파일에 저장되었습니다.")
else:
    print(f"✅ 이미 {len(hotel_links)}개의 호텔 링크가 존재하므로 새로 수집하지 않음.")

# ✅ 호텔 상세 정보 및 리뷰 수집 함수
def crawl_hotel_details(link, idx):
    #print(f"\n🔗 호텔 {idx + 1} 상세 페이지 진입: {link}")
    driver.get(link)
    time.sleep(3)

    hotel_info = {}

    hotel_info["detail_page_url"] = link

    try:
        hotel_name = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h1[data-selenium="hotel-header-name"]'))).text
    except:
        hotel_name = "호텔명 없음"

    hotel_info["hotel_name"] = hotel_name

    try:
        address = driver.find_element(By.CSS_SELECTOR, '[data-selenium="hotel-address-map"]').text
    except:
        address = "주소 없음"

    hotel_info["address"] = address

    try:
        paragraphs = driver.find_elements(By.XPATH,
                                          '//p[contains(@class, "Typographystyled__TypographyStyled-sc-j18mtu-0")]')
        hotel_desc = "\n".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 50])
    except:
        hotel_desc = ""

    hotel_info["description"] = hotel_desc

    try:
        rating_candidates = driver.find_elements(By.XPATH,
                                                 '//p[contains(@class, "Typographystyled__TypographyStyled-sc-j18mtu-0")]')
        for el in rating_candidates:
            text = el.text.strip()
            if re.match(r'^\d+(\.\d+)?$', text):
                hotel_info["rating"] = text
                break
    except:
        hotel_info["rating"] = ""

    try:
        price = driver.find_element(By.CSS_SELECTOR, '[data-element-name="final-price"]').text.replace("\n", "").strip()
    except:
        price = "가격 정보 없음"

    hotel_info["price"] = price

    # ✅ 리뷰 수집
    reviews_list = []
    page = 1

    while len(reviews_list) < 50:
        print(f"📄 {page}페이지 리뷰 수집 중...")
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.Review-comment')))
            reviews = driver.find_elements(By.CSS_SELECTOR, 'div.Review-comment')

            before_count = len(reviews_list)
            for review in reviews:
                try:
                    review_data = {}
                    try:
                        review_data["score"] = review.find_element(By.CLASS_NAME, 'Review-comment-leftScore').text
                    except:
                        review_data["score"] = ""
                    try:
                        review_data["score_text"] = review.find_element(By.CLASS_NAME,
                                                                        'Review-comment-leftScoreText').text
                    except:
                        review_data["score_text"] = ""
                    try:
                        review_data["title"] = review.find_element(By.CSS_SELECTOR, '[data-testid="review-title"]').text
                    except:
                        review_data["title"] = ""
                    try:
                        review_data["content"] = review.find_element(By.CSS_SELECTOR,
                                                                     '[data-testid="review-comment"]').text
                    except:
                        review_data["content"] = ""
                    try:
                        reviewer_text = review.find_element(By.CSS_SELECTOR,
                                                            '[data-info-type="reviewer-name"]').text.strip()
                        nickname, country = (reviewer_text.split("(")[0].strip(),
                                             reviewer_text.split("(")[1].replace(")",
                                                                                 "").strip()) if "(" in reviewer_text else (
                        reviewer_text, "정보 없음")
                        review_data["nickname"] = nickname
                        review_data["country"] = country
                    except:
                        review_data["nickname"] = ""
                        review_data["country"] = ""
                    try:
                        review_data["group_type"] = review.find_element(By.CSS_SELECTOR,
                                                                        '[data-info-type="group-name"]').text
                    except:
                        review_data["group_type"] = ""
                    try:
                        review_data["room_type"] = review.find_element(By.CSS_SELECTOR,
                                                                       '[data-info-type="room-type"]').text
                    except:
                        review_data["room_type"] = ""
                    try:
                        review_data["stay_info"] = review.find_element(By.CSS_SELECTOR,
                                                                       '[data-info-type="stay-detail"]').text
                    except:
                        review_data["stay_info"] = ""
                    try:
                        review_data["date"] = review.find_element(By.CSS_SELECTOR,
                                                                  '.Review-statusBar-left').text.replace("작성일: ", "")
                    except:
                        review_data["date"] = ""

                    reviews_list.append(review_data)

                    if len(reviews_list) >= 50:
                        break
                except Exception as e:
                    print("❗ 리뷰 파싱 중 오류 발생:", e)
                    continue

            after_count = len(reviews_list)
            if after_count == before_count:
                print("⛔️ 더 이상 새로운 리뷰 없음. 종료합니다.")
                break

            next_button = driver.find_elements(By.XPATH, f'//button[@aria-label="이용후기 페이지로 이동하기 {page + 1}"]')
            if next_button:
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button[0])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button[0])
                time.sleep(3)
                page += 1
            else:
                print("⛔️ 다음 페이지 없음. 리뷰 수집 종료")
                break

        except Exception as e:
            print("❗ 리뷰 수집 중 예외 발생:", e)
            break

    # ✅ 리뷰 최대 갯수 수집 후 저장
    if reviews_list:
        hotel_info["reviews"] = reviews_list
        all_hotels.append(hotel_info)
        collection.insert_one(hotel_info)
        visited_links.add(link)
        with open(visited_links_file, "w", encoding="utf-8") as f:
            json.dump(list(visited_links), f, ensure_ascii=False, indent=2)
        print(f"✅ MongoDB 및 visited_links 저장 완료: {hotel_name} (리뷰 {len(reviews_list)}건)")
    else:
        print(f"🚫 리뷰 없음 - 저장 생략: {hotel_name}")

all_links_list = hotel_links
link_index_map = {link: idx + 1 for idx, link in enumerate(all_links_list)}
for index, link in enumerate(all_links_list, start=1):
    if len(visited_links) >= 110:
        break
    if link in visited_links:
        continue
    print(f"\n🔗 전체 링크 중 {link_index_map[link]}번째 호텔 상세 페이지 진입: {link}")
    crawl_hotel_details(link, index)

# ✅ JSON 저장 (MongoDB에 저장된 전체 데이터 기준)
all_data = list(collection.find({}, {"_id": 0}))
with open("agoda_hotel_details.json", "w", encoding="utf-8") as f:
    f.write(json_util.dumps(all_data, ensure_ascii=False, indent=2))

print("\n✅ 모든 호텔 정보가 'agoda_hotel_details.json' 파일에 저장되었습니다.")

# ✅ MongoDB 저장 확인
print("\n📦 MongoDB 저장된 호텔 예시:")
for doc in collection.find().limit(3):
    print(doc)

driver.quit()