import streamlit as st
import re
from datetime import datetime
from io import StringIO
import pandas as pd

# --- 页面配置 ---
st.set_page_config(page_title="群聊成分分析器", page_icon="📊")

st.title("📊 QQ群聊成分分析器 (网页版)")
st.markdown("上传 txt 格式的聊天记录，分析谁是群里的“老司机”。")

# --- 侧边栏：设置 ---
with st.sidebar:
    st.header("⚙️ 参数设置")
    
    # 日期选择
    start_date = st.date_input("开始日期", value=datetime(2025, 1, 1))
    end_date = st.date_input("结束日期", value=datetime(2026, 1, 1))
    
    st.markdown("---")
    st.markdown("**特征词库设置** (词语用逗号或换行分隔)")
    
    # 词库输入
    w1_text = st.text_area("一级词库 (权重1)", "小姐姐, 妹子, 恋爱, 对象, 结婚", height=100)
    w1_val = st.number_input("一级权重", value=1)
    
    w2_text = st.text_area("二级词库 (权重3)", "腿, 胸, 白, 颜, 身材, 黑丝, 照", height=100)
    w2_val = st.number_input("二级权重", value=3)
    
    w3_text = st.text_area("三级词库 (权重5)", "冲, 涩, 烧, 硬, 导, 舔, 资源, 本子", height=100)
    w3_val = st.number_input("三级权重", value=5)

# --- 辅助函数：解析词库 ---
def parse_keywords(text, weight):
    keywords = {}
    if text:
        text = text.replace("\n", ",")
        words = [w.strip() for w in text.split(",") if w.strip()]
        for w in words:
            keywords[w] = weight
    return keywords

# --- 核心分析逻辑 ---
def analyze(file_content, s_date, e_date, keyword_dict):
    # 将日期转换为 datetime 对象以便比较
    s_date = datetime.combine(s_date, datetime.min.time())
    e_date = datetime.combine(e_date, datetime.min.time())
    
    user_scores = {}
    msg_counts = {}
    user_nicknames = {}
    user_hit_details = {}

    header_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)\((\d+)\)\s*$')
    date_format = "%Y-%m-%d %H:%M:%S"

    current_qq = None
    is_valid_time = False
    
    lines = file_content.splitlines()
    total_lines = len(lines)
    
    # 进度条
    progress_bar = st.progress(0)

    for i, line in enumerate(lines):
        # 更新进度条
        if i % 5000 == 0:
            progress_bar.progress(min(i / total_lines, 1.0))

        line = line.strip()
        match = header_pattern.match(line)
        
        if match:
            timestamp_str, nickname, qq = match.groups()
            try:
                msg_time = datetime.strptime(timestamp_str, date_format)
                if s_date <= msg_time < e_date:
                    is_valid_time = True
                    current_qq = qq
                    user_nicknames[qq] = nickname.strip()
                    if qq not in msg_counts:
                        msg_counts[qq] = 0
                        user_scores[qq] = 0
                        user_hit_details[qq] = {}
                    msg_counts[qq] += 1
                else:
                    is_valid_time = False
            except ValueError:
                continue
        
        elif is_valid_time and current_qq:
            if line.startswith("==="): continue
            
            for word, weight in keyword_dict.items():
                if word in line:
                    count = line.count(word)
                    user_scores[current_qq] += count * weight
                    if word not in user_hit_details[current_qq]:
                        user_hit_details[current_qq][word] = 0
                    user_hit_details[current_qq][word] += count
    
    progress_bar.empty() # 清除进度条

    # 整理结果
    results = []
    for qq, score in user_scores.items():
        m_count = msg_counts[qq]
        if score > 0 and m_count > 10: # 稍微降低门槛
            index = (score / m_count) * 100
            top_word = "无"
            if user_hit_details[qq]:
                top_word = max(user_hit_details[qq], key=user_hit_details[qq].get)
                
            results.append({
                '排名': 0, # 占位
                '昵称': user_nicknames[qq],
                'QQ号': qq,
                '欲望指数': round(index, 2),
                '加权总分': score,
                '发言总数': m_count,
                '高频词': top_word
            })
    return results

# --- 主界面：上传与显示 ---
uploaded_file = st.file_uploader("选择 QQ 导出文本文件 (.txt)", type="txt")

if uploaded_file is not None:
    # 尝试解码
    try:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        content = stringio.read()
    except:
        try:
            stringio = StringIO(uploaded_file.getvalue().decode("gb18030"))
            content = stringio.read()
        except:
            st.error("文件编码识别失败，请确保是 UTF-8 或 GBK 格式。")
            st.stop()

    # 构建词典
    full_dict = {}
    full_dict.update(parse_keywords(w1_text, w1_val))
    full_dict.update(parse_keywords(w2_text, w2_val))
    full_dict.update(parse_keywords(w3_text, w3_val))
    
    if st.button("开始分析", type="primary"):
        with st.spinner('正在分析中，请稍候...'):
            data = analyze(content, start_date, end_date, full_dict)
        
        if data:
            # 转换为 DataFrame
            df = pd.DataFrame(data)
            # 排序
            df = df.sort_values(by="欲望指数", ascending=False)
            #由于已经排序，重新生成排名列
            df['排名'] = range(1, len(df) + 1)
            # 调整列顺序
            df = df[['排名', '昵称', '欲望指数', '高频词', '加权总分', '发言总数', 'QQ号']]
            
            st.success(f"分析完成！找到 {len(df)} 位相关用户。")
            
            # 显示高亮表格
            st.dataframe(
                df, 
                hide_index=True,
                use_container_width=True,
                column_config={
                    "欲望指数": st.column_config.ProgressColumn(
                        "欲望指数",
                        help="分数越高，浓度越高",
                        format="%.2f",
                        min_value=0,
                        max_value=float(df['欲望指数'].max()),
                    ),
                }
            )
            
            # 显示图表
            st.subheader("📊 指数 Top 10 图表")
            top10 = df.head(10).set_index('昵称')
            st.bar_chart(top10['欲望指数'])
            
        else:
            st.warning("未找到符合条件的数据，请检查日期或词库。")