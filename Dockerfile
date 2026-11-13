# 데모 앱(Streamlit) 실행용 이미지
# - 검색 구성: 실험에서 고른 bge-m3 + row + title_body (.env.example 기본값과 같음)
# - 임베딩 모델과 인덱스는 빌드할 때 이미지에 넣는다(실행 시 다운로드 없음)
# - API 키는 이미지에 넣지 않는다. 실행할 때 --env-file .env로 넘긴다
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    EMBEDDING_PROVIDER=local \
    EMBEDDING_MODEL=BAAI/bge-m3 \
    CHUNKING_MODE=row \
    EMBEDDING_MODE=title_body \
    TOP_K=3 \
    GENERATION_PROVIDER=openai \
    GENERATION_MODEL=gpt-5.4-mini

WORKDIR /app

# CPU용 PyTorch를 먼저 설치해 GPU(CUDA) 패키지가 함께 설치되지 않게 한다
COPY requirements.txt .
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

COPY src/ src/
COPY app.py .
COPY data/faq_v2.csv data/faq_v2.csv

# 인덱스 생성: index/faq_v2/bge-m3 (모델 약 2.3GB 다운로드 포함)
# bge-m3 기본 브랜치에는 pytorch_model.bin만 있고, 처음 로딩할 때 PR 브랜치의 safetensors 변환본(2.2GB)을
# 추가로 받는다. 실행 중에는 오프라인이라 기본 브랜치의 .bin만 쓰므로, 같은 단계에서 PR 변환본을 지운다
RUN python src/indexing.py \
    && for ref in "$HF_HOME"/hub/models--*/refs/refs/pr/*; do \
         [ -f "$ref" ] || continue; \
         snap="$(dirname "$(dirname "$(dirname "$(dirname "$ref")")")")/snapshots/$(cat "$ref")"; \
         find "$snap" -type l -exec sh -c 'rm -f "$(readlink -f "$1")"' _ {} \; ; \
         rm -rf "$snap" "$ref"; \
       done

# 실행 중에는 모델을 내려받지 않는다(이미지에 넣은 모델만 사용)
ENV HF_HUB_OFFLINE=1

EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
