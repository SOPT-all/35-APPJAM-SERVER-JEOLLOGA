from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import mysql.connector
import yaml
import re
import time

def load_db_config(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            return config.get("database") if config else None
    except Exception as e:
        print(f"YAML 파일 로드 오류: {e}")
        return None

db_config_path = "C:\\jeolloga\\crawling\\db_config.yaml"
db_config = load_db_config(db_config_path)

if not db_config:
    print("DB 설정 로드 실패. 프로그램 종료")
    exit()

# DB에 temple_name, templestay, templestay_url 저장
def save_templestay_data_to_db(temple_name, templestay, templestay_url):
    try:
        conn = mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["name"]
        )
        cursor = conn.cursor()

        # 중복 여부 확인
        check_query = "SELECT COUNT(*) FROM url WHERE temple_name = %s AND templestay = %s"
        cursor.execute(check_query, (temple_name, templestay))
        count = cursor.fetchone()[0]

        if count == 0:
            query = "INSERT INTO url (temple_name, templestay, templestay_url) VALUES (%s, %s, %s)"
            cursor.execute(query, (temple_name, templestay, templestay_url))
            conn.commit()
            print(f"데이터 저장: 사찰명='{temple_name}', 템플스테이='{templestay}', URL='{templestay_url}'")
        else:
            print(f"사찰명 '{temple_name}' (템플스테이: '{templestay}')은 이미 존재합니다.")

    except mysql.connector.Error as e:
        print(f"데이터베이스 오류: {e}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def extract_templestay_data_with_paging(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.get(url)
        driver.implicitly_wait(10)

        while True:
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            listings = soup.find("div", {"id": "et-listings"})
            if listings:
                items = listings.find_all("li", {"class": "et-active-listing clearfix"})
                for item in items:
                    h3_tag = item.find("h3")
                    temple_name = None
                    templestay = None
                    if h3_tag:
                        match = re.search(r"\[(.*?)\]", h3_tag.text)
                        if match:
                            temple_name = match.group(1)
                        templestay = re.sub(r"\[.*?\]", "", h3_tag.text).strip()

                    link_tag = item.find("a", {"class": "temple-link"})
                    templestay_url = None
                    if link_tag and link_tag.get("href"):
                        base_url = "https://www.templestay.com"
                        templestay_url = base_url + link_tag["href"]

                    if temple_name and templestay and templestay_url:
                        save_templestay_data_to_db(temple_name, templestay, templestay_url)
                    else:
                        print(f"데이터 누락 - 사찰명: {temple_name}, 템플스테이명: {templestay}")

            try:
                next_button = driver.find_element(By.ID, "content_LinkNext")
                if "aspNetDisabled" in next_button.get_attribute("class"):
                    print("마지막 페이지에 도달했습니다.")
                    break
                else:
                    next_button.click()
                    time.sleep(2)
            except Exception as e:
                print(f"다음 페이지 버튼을 찾을 수 없습니다: {e}")
                break

    finally:
        driver.quit()

url = "https://www.templestay.com/reserv_search.aspx" 
extract_templestay_data_with_paging(url)