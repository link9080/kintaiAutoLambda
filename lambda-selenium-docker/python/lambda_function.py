import json
import time
import configparser
import requests
import os
from datetime import datetime, timedelta
from headless_chrome import create_driver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from TemplateInput import TemplateInput
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")  # 環境変数から取得
WAIT_TIME = 2

# Lambdaのデフォルトログハンドラーは既に設定されているので、
# 追加設定が不要なケースが多いが、フォーマット指定を追加する場合は以下
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# 設定ファイル読み込み
config = configparser.ConfigParser()
config.read('config.ini')

def format_to_yyyymmdd(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y/%m/%d").strftime("%Y%m%d")

def login_raku(driver, wait):
    driver.get(config['DEFAULT']['raku_url'])  # rakuurlの部分
    time.sleep(WAIT_TIME)
    logger.info(f"url:{driver.current_url}title:{driver.title}")
    # 企業IDを入力
    kigyo_element = wait.until(EC.presence_of_element_located((By.NAME, "loginId")))
    kigyo_element.send_keys(config['DEFAULT']['raku_login_id'])

    pass_element = wait.until(EC.presence_of_element_located((By.NAME, "password")))
    pass_element.send_keys(config['DEFAULT']['raku_password'])
    pass_element.send_keys(Keys.ENTER)

    time.sleep(WAIT_TIME)  # ページ遷移待ちなど適宜調整
    logger.info("ログイン成功")

    frame = wait.until(EC.presence_of_element_located((By.NAME, "main")))
    driver.switch_to.frame(frame)

def login_recoru(driver:webdriver, wait:WebDriverWait):
    try:
        # recoruのURLにアクセス
        driver.get(config['DEFAULT']['reco_url'])
        logger.info(f"url:{driver.current_url}title:{driver.title}")

        # 企業IDを入力
        kigyo_element = wait.until(lambda drv: drv.find_element(By.ID, "contractId"))
        kigyo_element.send_keys(config['DEFAULT']["reco_kigyo"])

        # メールアドレスを入力
        mail_element = wait.until(lambda drv: drv.find_element(By.ID, "authId"))
        mail_element.send_keys(config['DEFAULT']["reco_login_id"])

        # パスワードを入力してEnterキー
        pass_element = wait.until(lambda drv: drv.find_element(By.ID, "password"))
        pass_element.send_keys(config['DEFAULT']["reco_password"])
        pass_element.send_keys(Keys.ENTER)

        # 少し待機（ログイン処理のため）
        time.sleep(WAIT_TIME)
        logger.info("ログイン成功")

        # 「勤務表」リンクをクリック
        edit_page = wait.until(lambda drv: drv.find_element(By.LINK_TEXT, "勤務表"))
        edit_page.click()

        # ページ遷移のため少し待機
        time.sleep(WAIT_TIME)
        logger.info("勤務表")
    except Exception as e:
        logger.exception("recoruログイン処理でエラー発生")
        raise
def get_input_rakuraku_patterns(driver:webdriver, wait:WebDriverWait, input:TemplateInput = None):
    try:
        # 「交通費精算」が作成されていないか確認
        try:
            # 「ui-c-badge」の要素取得を試みる（タイムアウト時間で待つ）
            badges = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "ui-c-badge")))
            # 取得できた場合は最初の要素をクリック
            badges[0].click()
        except TimeoutException:
            # 「ui-c-badge」が見つからなかった場合は「交通費精算」のリンクをクリック
            newpage = wait.until(EC.presence_of_all_elements_located((By.LINK_TEXT, "交通費精算")))[0]
            newpage.click()

        time.sleep(WAIT_TIME)

        # ウィンドウ切り替え
        driver.switch_to.window(driver.window_handles[-1])
        logger.info("楽楽清算-一時保存")

        # 修正画面へ移動
        if "initializeView" not in driver.current_url:
            links = driver.find_elements(By.LINK_TEXT, "修正")
            if len(links) > 0:
                links[0].click()
            else:
                driver.find_element(By.CLASS_NAME, "w_denpyo_l").click()
            time.sleep(WAIT_TIME)
            driver.switch_to.window(driver.window_handles[-1])
        else:
            # 既に明細ウィンドウの場合
            pass

        logger.info("楽楽清算-通勤費画面")
        # 明細ウィンドウのハンドルを取得（最後のウィンドウ）
        meisai_window = wait.until(
            lambda drv: drv.window_handles[-1]
        )
        # 既存日付の取得
        try:
            daylists = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "labelColorDefault")))
        except TimeoutException:
            daylists = []
        
        created_days = [d.text for d in daylists]

        # マイパターンボタンをクリック
        meisai_insert_buttons = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".meisai-insert-button")))
        # ボタンの情報を出力
        logger.info(f"取得したmeisai-insert-buttonの数:{len(meisai_insert_buttons)}")
        target_found = False

        for idx, btn in enumerate(meisai_insert_buttons):
            logger.info(f"[{idx}] text: {btn.text}, tag: {btn.tag_name}, class: {btn.get_attribute('class')}")
            if "マイパターン" in btn.text:
                logger.info(f"→ マイパターンボタンをクリックします: index {idx}")
                btn.click()
                target_found = True
                break

        if not target_found:
            logger.info("マイパターンボタンが見つかりませんでした。")

        time.sleep(WAIT_TIME)
        driver.switch_to.window(driver.window_handles[-1])
        logger.info(f"ウィンドウ数: {len(driver.window_handles)}")
        logger.info(f"現在のURL: {driver.current_url}")
        logger.info(f"タイトル: {driver.title}")


        # チェックボックス情報を取得
        trs = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "d_hover")))
        raku_ptns = []

        for tr in trs:
            ptn = {}
            checkbox = tr.find_element(By.NAME, "kakutei")
            ptn['id'] = checkbox.get_attribute("value")
            tds = tr.find_elements(By.TAG_NAME, "td")
            if len(tds) > 1:
                ptn['ptn_name'] = tds[1].text
            raku_ptns.append(ptn)
        
        if input:
            logger.info("入力開始")
            # 在宅フラグ設定
            for ptn in raku_ptns:
                ptn['zaitaku'] = False  # 初期化
                if ptn['ptn_name'] == "在宅" and ptn['id'] in (input.rakuraku1, input.rakuraku2):
                    input.zaitaku = True
                    break
            already_registered = any(d.startswith(input.date) for d in created_days)
            if already_registered:
                logger.info(input.date+"入力済")
                return "すでに楽々精算に入力済の日付です\n楽楽精算入力終了します。"
            if input.rakuraku1:
                # チェックボックスを取得して選択
                chks = wait.until(EC.presence_of_all_elements_located((By.NAME, "kakutei")))
                for chk in chks:
                    if chk.get_attribute("value") == input.rakuraku1:
                        chk.click()
                        break

                # 次へクリック
                nextbtn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".common-btn.accesskeyFix.kakutei.d_marginLeft5")))
                nextbtn.click()

                time.sleep(WAIT_TIME)

                # 日付入力
                date_inputs = wait.until(EC.presence_of_all_elements_located((By.NAME, "meisaiDate")))
                date_inputs[1].send_keys(input.date)

                # 明細追加押下
                nextbtn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".button.button--l.button-primary.accesskeyFix.kakutei")))
                nextbtn.click()

                time.sleep(WAIT_TIME)

                driver.switch_to.window(meisai_window)

                # マイパターンボタンをクリック
                meisai_insert_buttons = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".meisai-insert-button")))
                # ボタンの情報を出力
                logger.info(f"取得したmeisai-insert-buttonの数:{len(meisai_insert_buttons)}")
                target_found = False

                for idx, btn in enumerate(meisai_insert_buttons):
                    logger.info(f"[{idx}] text: {btn.text}, tag: {btn.tag_name}, class: {btn.get_attribute('class')}")
                    if "マイパターン" in btn.text:
                        logger.info(f"→ マイパターンボタンをクリックします: index {idx}")
                        btn.click()
                        target_found = True
                        break
                time.sleep(WAIT_TIME)
                driver.switch_to.window(driver.window_handles[-1])

            if input.rakuraku2:
                    # チェックボックスを取得して選択
                    chks = wait.until(EC.presence_of_all_elements_located((By.NAME, "kakutei")))
                    for chk in chks:
                        if chk.get_attribute("value") == input.rakuraku2:
                            chk.click()
                            break

                    # 次へクリック
                    nextbtn = wait.until(EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".common-btn.accesskeyFix.kakutei.d_marginLeft5")))
                    nextbtn.click()

                    time.sleep(WAIT_TIME)

                    # 日付入力
                    date_inputs = wait.until(EC.presence_of_all_elements_located((By.NAME, "meisaiDate")))
                    date_inputs[1].send_keys(input.date)

                    # 明細追加押下
                    nextbtn = wait.until(EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".button.button--l.button-primary.accesskeyFix.kakutei")))
                    nextbtn.click()

                    time.sleep(WAIT_TIME)

                    driver.switch_to.window(meisai_window)

                    # マイパターンボタンをクリック
                    meisai_insert_buttons = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".meisai-insert-button")))
                    # ボタンの情報を出力
                    logger.info(f"取得したmeisai-insert-buttonの数:{len(meisai_insert_buttons)}")
                    target_found = False

                    for idx, btn in enumerate(meisai_insert_buttons):
                        logger.info(f"[{idx}] text: {btn.text}, tag: {btn.tag_name}, class: {btn.get_attribute('class')}")
                        if "マイパターン" in btn.text:
                            logger.info(f"→ マイパターンボタンをクリックします: index {idx}")
                            btn.click()
                            target_found = True
                            break
                    time.sleep(WAIT_TIME)
                    driver.switch_to.window(driver.window_handles[-1])
            # 「common-btn accesskeyClose」ボタンが存在するかチェック
            close_buttons = WebDriverWait(driver, 10).until(
                lambda drv: drv.find_elements(By.CSS_SELECTOR, ".common-btn.accesskeyClose")
            )

            if len(close_buttons) > 0:
                close_buttons[0].click()
                time.sleep(WAIT_TIME)  # ChromeDriverUtil.sleep() の代わり
                window = WebDriverWait(driver, 10).until(lambda drv: drv.window_handles[-1])
                driver.switch_to.window(window)

            # 「button save accesskeyReturn」ボタンが存在するかチェックしてクリック
            save_buttons = WebDriverWait(driver, 10).until(
                lambda drv: drv.find_elements(By.CSS_SELECTOR, ".button.save.accesskeyReturn")
            )

            if len(save_buttons) > 0:
                save_buttons[0].click()
    except TimeoutException as te:
        logger.info(te)
        raise
    except NoSuchElementException as ne:
        logger.info(ne)
        raise
    except Exception as e:
        logger.info(e)
        raise
    return raku_ptns

def input_recoru(driver:webdriver, wait:WebDriverWait, input:TemplateInput):
    try:
        tr_class = f"1717-{format_to_yyyymmdd(input.date)}"  # 適宜クラス名補正
        _tr = wait.until(lambda drv: drv.find_element(By.CSS_SELECTOR, f"[class='{tr_class}']"))

        # 開始
        if input.start:
            # 勤務区分
            kbn = _tr.find_element(By.TAG_NAME, "select")
            select = Select(kbn)
            opt = select.first_selected_option.get_attribute("value")

            if not opt:
                if input.zaitaku:
                    select.select_by_index(2)
                    logger.info(f"勤務区分に『{select.first_selected_option.text}』を選択（在宅）")
                else:
                    select.select_by_index(1)
                    logger.info(f"勤務区分に『{select.first_selected_option.text}』を選択（出社）")
            else:
                logger.info(f"既に勤務区分に『{select.first_selected_option.text}』が選択されている")

            start_class_prefix = f"ID-worktimeStart-{format_to_yyyymmdd(input.date)}-1"
            candidates = [
                f"{start_class_prefix} worktimeStart timeText edited",
                f"{start_class_prefix} bg-err worktimeStart timeText edited",
                f"{start_class_prefix} bg-err worktimeStart timeText",
                f"{start_class_prefix} worktimeStart timeText"
            ]

            for cls in candidates:
                elements = _tr.find_elements(By.CSS_SELECTOR, f"[class='{cls}']")
                logger.debug(f"クラス '{cls}' の要素数: {len(elements)}")
                if elements:
                    logger.info(f"勤務開始入力用の要素をクラス '{cls}' で発見")
                    start = elements[0]
                    start.clear()
                    start.send_keys(input.start)
                    logger.info(f"勤務開始時間を {start.get_attribute('value')} に設定しました")
                    break
            else:
                logger.warning("勤務開始の入力欄が見つかりませんでした")

        # 終了
        if input.end:
            end_class_prefix = f"ID-worktimeEnd-{format_to_yyyymmdd(input.date)}-1"
            candidates = [
                f"{end_class_prefix} worktimeEnd timeText edited",
                f"{end_class_prefix} bg-err worktimeEnd timeText edited",
                f"{end_class_prefix} bg-err worktimeEnd timeText",
                f"{end_class_prefix} worktimeEnd timeText"
            ]

            for cls in candidates:
                elements = _tr.find_elements(By.CSS_SELECTOR, f"[class='{cls}']")
                if elements:
                    logger.info(f"勤務終了入力用の要素をクラス '{cls}' で発見")
                    end = elements[0]
                    end.clear()
                    end.send_keys(input.end)
                    logger.info(f"勤務終了時間を {end.get_attribute('value')} に設定しました")
                    break
        # 休憩
        if input.break_start:
            logger.info("休憩入力")
            breakTimewrite(_tr, driver, wait, input)
        try:
            # 更新ボタンを待機してクリック
            updbtn = wait.until(lambda drv: drv.find_element(By.ID, "UPDATE-BTN"))
            updbtn.click()
            logger.info("更新ボタンをクリックしました")

            # アラートが表示されるのを待つ → クリックが効いた証拠になる
            alert = wait.until(EC.alert_is_present())
            logger.info(" アラートを検出しました：ボタン押下に成功")
            alert.accept()

        except TimeoutException:
            logger.info("アラートが表示されませんでした。更新ボタンのクリックが反映されなかった可能性があります")
        
    except TimeoutException as e:
        logger.exception(e)
        logger.info(f"現在のURL: {driver.current_url}")
        logger.info(f"タイトル: {driver.title}")
        logger.debug(driver.page_source[:1000])  # ソースが長いときは先頭のみ
        raise

    time.sleep(WAIT_TIME)  
def breakTimewrite(_tr, driver:webdriver, wait:WebDriverWait, input:TemplateInput):
    try:
        # 休憩編集アイコンを取得
        break_time = _tr.find_element(By.CSS_SELECTOR, "[class='ow btn-edit tip']")
        imgs = break_time.find_elements(By.TAG_NAME, "img")

        # 画像をクリック（要素数によって分岐）
        if len(imgs) != 1:
            imgs[1].click()
        else:
            imgs[0].click()

        time.sleep(WAIT_TIME)  # ChromeDriverUtil.sleep() の代替
        logger.info("休憩画面")

        # 休憩開始時間入力
        logger.info("休憩開始入力")
        kyustr = wait.until(EC.presence_of_element_located((By.ID, "breaktimeDtos[0].breaktimeStart")))
        kyustr.clear()
        kyustr.send_keys(input.break_start)

        # 休憩終了時間を計算して入力
        logger.info("休憩終了入力")
        kyuend = wait.until(EC.presence_of_element_located((By.ID, "breaktimeDtos[0].breaktimeEnd")))
        kyuend.clear()

        # Python側のCalcKyukei関数（別途定義が必要）
        kyu_end_calc = calc_kyukei(input)
        kyuend.send_keys(kyu_end_calc)
        logger.info(f"休憩終了{kyu_end_calc}入力完了")

        # 更新ボタンをクリック（2番目の要素）
        update_buttons = wait.until(EC.presence_of_all_elements_located((By.ID, "UPDATE-BTN")))
        update_buttons[1].click()

        # アラートが表示されるのを待つ → クリックが効いた証拠になる
        alert = wait.until(EC.alert_is_present())
        logger.info(" アラートを検出しました：ボタン押下に成功")
        alert.accept()

        time.sleep(WAIT_TIME) 

        # 「閉じる」ボタンが存在すればクリック
        close_buttons = driver.find_elements(By.CSS_SELECTOR, ".common-btn.close")
        if close_buttons:
            try:
                close_buttons[0].click()
                logger.info("✅ 閉じるボタンをクリックしました")
            except Exception as e:
                logger.info(f"❗ クリック時にエラー: {e}")
        else:
            logger.info("⚠️ 閉じるボタンは存在しませんでした")
        time.sleep(WAIT_TIME)  # ChromeDriverUtil.sleep() の代替
    except TimeoutException:
        logger.info(f"現在のURL: {driver.current_url}")
        logger.info(f"タイトル: {driver.title}")
        logger.debug(driver.page_source[:1000])  # ソースが長いときは先頭のみ
        raise

def calc_kyukei(input:TemplateInput):
    HOUTEI_TIME = float(config["DEFAULT"]["houtei"])
    def parse_time_string(time_str):
        """ 'HHmm' または 'HH:mm' を datetime に変換 """
        try:
            if len(time_str) == 4 and time_str.isdigit():
                return datetime.strptime(time_str, "%H%M")
            else:
                return datetime.strptime(time_str, "%H:%M")
        except ValueError:
            raise ValueError(f"時間形式が不正です: {time_str}")

    str_time = parse_time_string(input.start)
    end_time = parse_time_string(input.end)
    kyu_str_time = parse_time_string(input.break_start)

    work_duration = end_time - str_time

    # 勤務時間に応じて休憩時間を加算
    if work_duration >= timedelta(hours=HOUTEI_TIME):
        kyu_end = kyu_str_time + timedelta(minutes=60)
    else:
        kyu_end = kyu_str_time + timedelta(minutes=45)

    return kyu_end.strftime("%H:%M")





def initChrome():
    driver = None  # ← 先に初期化
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 20)

        return driver, wait
    except Exception as e:
        logger.exception("Chromeの初期化に失敗しました。")
        raise


def lambda_handler(event, context):
    try:
        logger.info("受信イベント: %s", json.dumps(event))

        if 'body' in event:
            body = json.loads(event['body'])
        else:
            logger.error("eventに'body'が含まれていません: %s", json.dumps(event))
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'body' in event"})
            }

        # 疎通確認などで events が空の場合はOKを返す
        if not body.get('events'):
            logger.info("空の events を受信しました（疎通確認など）")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "OK"})
            }

        line_event = body['events'][0]
        reply_token = line_event.get('replyToken', "")
        user_message = line_event.get('message', {}).get('text', '')
        if not user_message:
            logger.info("テキスト以外を受信")
            reply_message(reply_token,"テキストメッセージのみ受付けます。")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "OK"})
            }
        user_id = body['events'][0]['source']['userId']
        logger.info(f"Reply Token: {reply_token}")
        logger.info(f"User ID: {user_id}")
        input: TemplateInput = TemplateInput.create(user_message)
        logger.info("入力: %s", vars(input))

        if "楽楽精算パターン取得" in user_message:
            reply_message(reply_token,"パターン取得中")

            logger.info("Chrome起動開始")
            driver, wait = initChrome()
            logger.info("Chrome初期化成功")
            logger.info("楽楽精算にログイン開始")
            login_raku(driver, wait)
            logger.info("楽楽精算にログイン完了")
            logger.info("パターン取得開始")
            raku_ptns = get_input_rakuraku_patterns(driver, wait)
            logger.info("パターン取得完了")
            driver.quit()
            pushText = "取得したパターン:\n" + "\n".join([f"{ptn['id']}: {ptn['ptn_name']}" for ptn in raku_ptns])
            logger.info(pushText)
            push_message(user_id,pushText)

        elif input.is_valid():
            reply_message(reply_token,"処理開始")
            driver, wait = initChrome()
            logger.info("Chrome起動完了")
            input.date = datetime.strptime(f"{datetime.now().year}-{input.date}", "%Y-%m-%d").strftime("%Y/%m/%d")
            logger.info(f"整形済み日付: {input.date}")
            logger.info("楽楽精算にログイン開始")
            login_raku(driver, wait)
            logger.info("楽楽精算にログイン完了")
            logger.info("パターン入力開始")
            rtn_message = get_input_rakuraku_patterns(driver, wait, input)
            if isinstance(rtn_message, str) and rtn_message.strip():
                push_message(user_id, f"{input.date}\n{rtn_message}")
            else:
                push_message(user_id, f"{input.date}\n楽楽精算入力完了")
            driver.quit()
            driver, wait = initChrome()
            login_recoru(driver, wait)
            input_recoru(driver, wait, input)
            driver.quit()
            push_message(user_id, f"{input.date}\nrecoru入力完了")

        elif "テンプレート" in user_message:
            reply_text = str(input)
            reply_message(reply_token, "メッセージを受け付けました。")
            logger.info(reply_text)
            push_message(user_id,reply_text)

        else:
            reply_text = "「楽楽精算パターン取得」と入力するとパターン一覧を取得します。\n「テンプレート」と入力すると入力テンプレートを取得します。"
            reply_message(reply_token, "メッセージを受け付けました。")
            logger.info(reply_text)
            push_message(user_id,reply_text)
        # OKレスポンス
        return {"statusCode": 200, "body": "OK"}
    except Exception as e:
        logger.exception(e)
        push_message(user_id, f"エラーになりました。再度メッセージを送信してください\n{e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Missing 'body' in event"})
        }

def reply_message(reply_token, text):
    if not LINE_CHANNEL_ACCESS_TOKEN: return
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [{
            "type": "text",
            "text": text
        }]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        logger.error("LINE返信失敗: %s", response.text)
    else:
        logger.info(f"LINEに返信しました{text}")

def push_message(user_id: str, text: str):
    if not LINE_CHANNEL_ACCESS_TOKEN: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    body = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    response = requests.post(url, headers=headers, json=body)

    if response.status_code != 200:
        logger.error(f"LINE Push失敗: {response.status_code} {response.text}")
    else:
        logger.info(f"LINE Push成功{text}")

if __name__ == "__main__":
    message_text = """日付: 6-17
開始:0900
終了:1830
休憩開始:1200
楽楽精算1:0_8365
楽楽精算2:0_10096"""

    mock_event = {
        "body": json.dumps({
            "events": [
                {
                    "type": "message",
                    "replyToken": "test_reply_token",
                    "source": {
                        "userId": "U1234567890abcdef1234567890abcdef",
                        "type": "user"
                    },
                    "timestamp": 1650000000000,
                    "mode": "active",
                    "message": {
                        "type": "text",
                        "id": "1234567890",
                        "text": message_text
                    }
                }
            ]
        })
    }

    response = lambda_handler(mock_event, {})
    print(response)