FROM public.ecr.aws/lambda/python:3.10

# 必要なパッケージのインストール
RUN yum -y install unzip curl wget tar \
 && yum -y install libX11 GConf2 alsa-lib atk cups-libs gtk3 \
    libXcomposite libXcursor libXdamage libXext libXi libXtst \
    pango xorg-x11-fonts-Type1 xorg-x11-fonts-misc

# Chrome のインストール
RUN curl -SL https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm -o chrome.rpm \
 && yum -y localinstall chrome.rpm \
 && mkdir -p /opt/chrome \
 && cp -r /opt/google/chrome/* /opt/chrome/ \
 && rm -rf /opt/google

# ChromeDriver のインストール（Chromeバージョンに合わせる）
RUN curl -SL https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.103/linux64/chromedriver-linux64.zip -o chromedriver.zip \
 && unzip chromedriver.zip \
 && mv chromedriver-linux64/chromedriver /opt/chromedriver \
 && chmod +x /opt/chromedriver \
 && rm -f chromedriver.zip

# Pythonライブラリのインストール
COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}" 

# Lambda関数のコピー
COPY lambda_function.py ${LAMBDA_TASK_ROOT}
COPY TemplateInput.py ${LAMBDA_TASK_ROOT}
COPY config.ini ${LAMBDA_TASK_ROOT}/config.ini

# エントリポイント
CMD ["lambda_function.lambda_handler"]
