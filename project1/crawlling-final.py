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

# ✅ 브라우저 설정
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# ✅ 아고다 호텔 목록 페이지 (지역은 추후 링크로 대체)
driver.get("https://www.agoda.com/ko-kr/search?city=16901")

hotel_links = set()
scroll_pause = 2
same_count = 0
max_same = 3
last_height = 0

print("🚀 스크롤 시작")

# ✅ 전체 호텔 데이터 저장 리스트
all_hotels = []

# ✅ 구조 감지 + 링크 수집 함수
def extract_hotel_links():
    links = set()

    # 1. 최신 구조: data-testid="property-name-link"
    hotel_elements = driver.find_elements(By.CSS_SELECTOR, 'a[data-testid="property-name-link"]')
    if hotel_elements:
        print("✅ 구조 감지: a[data-testid='property-name-link'] 사용")
    else:
        # 2. 예전 구조: data-selenium="hotel-name"
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
        if len(hotel_links) >= 100:
            print("✅ 호텔 100개 수집 완료. 중단합니다.")
            break

    after = len(hotel_links)
    print(f"🔎 현재 누적 수집 호텔 수: {after}")

    if len(hotel_links) >= 100:
        break

    if after == before:
        same_count += 1
        if same_count >= max_same:
            print("✅ 더 이상 로딩되지 않음. 종료.")
            break
    else:
        same_count = 0

print(f"\n🏨 최종 수집된 호텔 링크 수: {len(hotel_links)}")

# ✅ 호텔 상세 정보 및 리뷰 수집 함수
def crawl_hotel_details(link):
    print(f"\n🔗 호텔 상세 페이지 진입: {link}")
    driver.get(link)
    time.sleep(3)

    hotel_info = {}

    try:
        hotel_name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1[data-selenium="hotel-header-name"]'))).text
    except:
        hotel_name = "호텔명 없음"

    hotel_info["hotel_name"] = hotel_name

    try:
        address = driver.find_element(By.CSS_SELECTOR, '[data-selenium="hotel-address-map"]').text
    except:
        address = "주소 없음"

    hotel_info["address"] = address

    try:
        paragraphs = driver.find_elements(By.XPATH, '//p[contains(@class, "Typographystyled__TypographyStyled-sc-j18mtu-0")]')
        hotel_desc = "\n".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 50])
    except:
        hotel_desc = ""

    hotel_info["description"] = hotel_desc

    try:
        rating_candidates = driver.find_elements(By.XPATH, '//p[contains(@class, "Typographystyled__TypographyStyled-sc-j18mtu-0")]')
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
    while page <= 2 and len(reviews_list) < 50:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ol.Review-comments')))
            reviews = driver.find_elements(By.CSS_SELECTOR, 'ol.Review-comments > li')
            for review in reviews:
                try:
                    title = review.find_element(By.CSS_SELECTOR, '[data-testid="review-title"]').text
                    content = review.find_element(By.CSS_SELECTOR, '[data-testid="review-comment"]').text
                    reviewer_text = review.find_element(By.CSS_SELECTOR, '[data-info-type="reviewer-name"]').text.strip()
                    nickname, country = (reviewer_text.split("(")[0].strip(), reviewer_text.split("(")[1].replace(")", "").strip()) if "(" in reviewer_text else (reviewer_text, "정보 없음")
                    group_type = review.find_element(By.CSS_SELECTOR, '[data-info-type="group-name"]').text
                    room_type = review.find_element(By.CSS_SELECTOR, '[data-info-type="room-type"]').text
                    stay_info = review.find_element(By.CSS_SELECTOR, '[data-info-type="stay-detail"]').text
                    date = review.find_element(By.CSS_SELECTOR, '.Review-statusBar-left').text.replace("작성일: ", "")
                    reviews_list.append({
                        "title": title,
                        "content": content,
                        "nickname": nickname,
                        "country": country,
                        "group_type": group_type,
                        "room_type": room_type,
                        "stay_info": stay_info,
                        "date": date
                    })
                    if len(reviews_list) >= 50:
                        break
                except:
                    continue
            if len(reviews_list) >= 50:
                break
            next_button = driver.find_elements(By.XPATH, f'//button[@aria-label="이용후기 페이지로 이동하기 {page + 1}"]')
            if next_button:
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button[0])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button[0])
                time.sleep(3)
                page += 1
            else:
                break
        except:
            break

    hotel_info["reviews"] = reviews_list
    all_hotels.append(hotel_info)

# ✅ 상세 페이지 순회
for link in hotel_links:
    crawl_hotel_details(link)

# ✅ JSON 저장
with open("agoda_hotel_details.json", "w", encoding="utf-8") as f:
    json.dump(all_hotels, f, ensure_ascii=False, indent=2)

print("\n✅ 모든 호텔 정보가 'agoda_hotel_details.json' 파일에 저장되었습니다.")
driver.quit()
