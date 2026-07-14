import streamlit as st
import pandas as pd
import numpy as np
import re
from googleapiclient.discovery import build
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(
    page_title="유튜브 댓글 분석기 & 워드클라우드",
    page_icon="🎬",
    layout="wide"
)

# 스타일 적용 (한글 폰트 깨짐 방지 및 시각화 배경 톤 정리)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

# 2. API 키 로드 (로컬 테스트용 입력창 제공 + 스트림릿 Secrets 환경 변수 연동)
# 스트림릿 클라우드의 'Settings' -> 'Secrets' 탭에 YOUTUBE_API_KEY="내키" 형태로 저장하세요.
if "YOUTUBE_API_KEY" in st.secrets:
    api_key = st.secrets["YOUTUBE_API_KEY"]
else:
    api_key = st.sidebar.text_input("YouTube API Key를 입력하세요 (Secrets 미설정 시)", type="password")

# 3. 유튜브 영상 ID 추출 함수
def extract_video_id(url):
    pattern = r'(?:v=|\/shorts\/|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# 4. 유튜브 댓글 수집 함수
@st.cache_data(show_spinner="유튜브에서 댓글을 가져오는 중입니다...")
def get_youtube_comments(video_id, api_key, max_results=100):
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        comments = []
        
        # 첫 페이지 요청
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            textFormat="plainText"
        )
        response = request.execute()

        while response and len(comments) < max_results:
            for item in response['items']:
                comment_data = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment_data['authorDisplayName'],
                    'text': comment_data['textDisplay'],
                    'like_count': comment_data['likeCount'],
                    'published_at': comment_data['publishedAt']
                })
                if len(comments) >= max_results:
                    break
            
            # 다음 페이지 토큰이 있고 목표치에 도달하지 않았다면 계속 수집
            if 'nextPageToken' in response and len(comments) < max_results:
                request = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    pageToken=response['nextPageToken'],
                    maxResults=min(max_results - len(comments), 100),
                    textFormat="plainText"
                )
                response = request.execute()
            else:
                break
                
        return pd.DataFrame(comments)
    except Exception as e:
        st.error(f"API 요청 중 에러가 발생했습니다: {e}")
        return pd.DataFrame()

# 5. 한글 중심의 텍스트 클리닝 및 워드클라우드용 텍스트 가공
def clean_and_join_text(text_series):
    # 특수문자 및 자음/모음 단독 표기 제거 (ㅋㅋㅋ, ㅎㅎㅎ 등은 살리거나 제거 조절 가능)
    # 아래 정규식은 기본 한글, 영어, 숫자만 남겨둡니다.
    cleaned_texts = []
    for text in text_series:
        if not isinstance(text, str):
            continue
        text = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text)
        cleaned_texts.append(text)
    
    combined_text = " ".join(cleaned_texts)
    
    # 일반적인 조사, 대명사 등 무의미한 단어 필터링 리스트 (불용어 정의)
    stopwords = set([
        "진짜", "너무", "이거", "정말", "보고", "이게", "그냥", "하고", "하는", "영상", "유튜브", "구독",
        "좋아요", "많이", "있는", "있네요", "같아요", "생각", "사람", "합니다", "봤는데", "다들", "아닌"
    ])
    
    # 띄어쓰기 기준으로 쪼갠 후 불용어 필터링
    filtered_words = [word for word in combined_text.split() if word not in stopwords and len(word) > 1]
    return " ".join(filtered_words)

# 6. UI 타이틀
st.title("🎬 YouTube 댓글 분석 및 워드 클라우드")
st.markdown("유튜브 비디오 링크를 입력하여 시청자들의 반응과 주요 키워드를 한눈에 분석해 보세요.")

if not api_key:
    st.info("💡 사이드바 혹은 Streamlit Secrets에 `YOUTUBE_API_KEY`를 먼저 설정해 주세요.")
else:
    # 7. 입력 폼 영역
    col_input, col_num = st.columns([3, 1])
    with col_input:
        video_url = st.text_input("유튜브 동영상 또는 쇼츠 URL을 입력하세요", placeholder="https://www.youtube.com/watch?v=...")
    with col_num:
        max_comments = st.number_input("가져올 최대 댓글 수", min_value=10, max_value=500, value=100, step=50)

    if video_url:
        video_id = extract_video_id(video_url)
        
        if video_id:
            df = get_youtube_comments(video_id, api_key, max_comments)
            
            if not df.empty:
                st.success(f"성공적으로 {len(df)}개의 댓글을 불러왔습니다!")
                
                # 메인 탭 분할
                tab1, tab2, tab3 = st.tabs(["✨ 워드 클라우드", "📊 댓글 통계", "📋 전체 댓글"])
                
                with tab1:
                    st.subheader("🗣️ 핵심 키워드 트렌드 (Word Cloud)")
                    
                    # 텍스트 데이터 가공
                    word_cloud_text = clean_and_join_text(df['text'])
                    
                    if word_cloud_text.strip():
                        # 워드클라우드 스타일 구성 (눈이 편안하면서 트렌디한 다크 계열 레이아웃)
                        wc = WordCloud(
                            width=1000,
                            height=500,
                            background_color="#1E1E1E", # 트렌디한 다크 그레이 배경
                            colormap="cool",            # 세련된 블루/퍼플 톤의 그라데이션
                            max_words=100,
                            font_path=None              # 스트림릿 클라우드의 기본 영문/한글 폴백 폰트 적용
                        ).generate(word_cloud_text)
                        
                        fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1E1E1E')
                        ax.imshow(wc, interpolation='bilinear')
                        ax.axis("off")
                        plt.tight_layout(pad=0)
                        
                        st.pyplot(fig)
                        st.caption("※ 빈도가 높은 단어일수록 글씨가 크게 표시됩니다. 조사 및 무의미한 단어는 필터링되었습니다.")
                    else:
                        st.warning("워드클라우드를 만들 수 있는 의미 있는 텍스트 단어가 부족합니다.")

                with tab2:
                    st.subheader("👍 가장 호응이 좋은 베스트 댓글 TOP 5")
                    # 좋아요 순으로 정렬
                    best_comments = df.sort_values(by='like_count', ascending=False).head(5)
                    for idx, row in best_comments.iterrows():
                        st.info(f"**{row['author']}** (👍 {row['like_count']}개)\n\n{row['text']}")
                    
                    st.markdown("---")
                    
                    # 좋아요 분포 차트
                    st.subheader("📈 댓글 좋아요 분포")
                    fig_likes = px.histogram(
                        df, 
                        x='like_count', 
                        nbins=20, 
                        title="댓글당 좋아요 수 분포", 
                        labels={'like_count': '좋아요 수', 'count': '댓글 수'},
                        color_discrete_sequence=['#FF4B4B']
                    )
                    st.plotly_chart(fig_likes, use_container_width=True)

                with tab3:
                    st.subheader("💬 수집된 댓글 목록")
                    st.dataframe(df[['author', 'text', 'like_count', 'published_at']], use_container_width=True)
            else:
                st.warning("가져온 댓글이 없거나 올바르지 않은 비디오 ID입니다. 동영상의 댓글 사용 설정 상태를 확인해 보세요.")
        else:
            st.error("유튜브 URL 주소 형식에서 비디오 ID를 추출하지 못했습니다. 정확한 주소를 입력해 주세요.")
