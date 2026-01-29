import streamlit as st
import re
from datetime import datetime
from io import StringIO
import pandas as pd
import os

# --- 页面配置 ---
st.set_page_config(page_title="群聊成分分析器 Pro", page_icon="📊", layout="wide")

st.title("📊 QQ群聊成分分析器 Pro")
st.markdown("上传 txt 格式的聊天记录，基于多维度模型分析群成员成分。")

# --- 侧边栏：设置 ---
with st.sidebar:
    st.header("⚙️ 参数设置")
    
    # 日期选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime(2025, 1, 1))
    with col2:
        end_date = st.date_input("结束日期", value=datetime(2026, 1, 1))
    
    st.markdown("---")
    st.subheader("🔍 分析模型选择")

    # --- 新增功能：读取维度文件 ---
    # 默认值
    default_w1 = "谢谢,辛苦,抱歉,关心,问候,加油,理解,尊重,支持,平安"
    default_w2 = "帮助,感同身受,善良,温柔,照顾,体谅,包容,治愈,宽容,暖心"
    default_w3 = "牺牲,慈悲,救赎,大爱,虔诚,无私,奉献,怜悯,普渡,至善"
    current_dim_name = "同理心" # 默认指标名称

    try:
        # 尝试读取同目录下的 csv
        if os.path.exists("dimension.csv"):
            df_dim = pd.read_csv("dimension.csv")
            # 获取所有维度名称
            dim_options = df_dim["维度"].tolist()
            # 下拉选择框
            selected_dim = st.selectbox("选择分析维度", dim_options)
            
            # 根据选择获取对应行的关键词
            row = df_dim[df_dim["维度"] == selected_dim].iloc[0]
            
            # 更新默认值
            default_w1 = row["1级加权(1分-潜意识)"]
            default_w2 = row["2级加权(3分-明显)"]
            default_w3 = row["3级加权(5分-极端)"]
            current_dim_name = selected_dim
        else:
            st.warning("未检测到 dimension.csv，使用默认老司机模式。")
    except Exception as e:
        st.error(f"读取维度文件出错: {e}")

    st.markdown(f"**当前模式：{current_dim_name}分析** (可下方微调关键词)")
    
    # 词库输入 (使用 value 参数动态更新)
    w1_text = st.text_area("一级词库 (权重1 - 潜意识)", value=default_w1, height=100)
    w1_val = st.number_input("一级权重", value=1)
    
    w2_text = st.text_area("二级词库 (权重3 - 明显)", value=default_w2, height=100)
    w2_val = st.number_input("二级权重", value=3)
    
    w3_text = st.text_area("三级词库 (权重5 - 极端)", value=default_w3, height=100)
    w3_val = st.number_input("三级权重", value=5)

# --- 辅助函数：解析词库 ---
def parse_keywords(text, weight):
    keywords = {}
    if text:
        # 兼容中文逗号和英文逗号，以及换行符
        text = text.replace("\n", ",").replace("，", ",")
        words = [w.strip() for w in text.split(",") if w.strip()]
        for w in words:
            keywords[w] = weight
    return keywords

# --- 核心分析逻辑 ---
def analyze(file_content, s_date, e_date, keyword_dict, index_name):
    # 将日期转换为 datetime 对象以便比较
    s_date = datetime.combine(s_date, datetime.min.time())
    e_date = datetime.combine(e_date, datetime.min.time())
    
    user_scores = {}
    msg_counts = {}
    user_nicknames = {}
    user_hit_details = {}

    # 优化正则：兼容部分不同格式的QQ导出头
    header_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)\((\d+)\)\s*$')
    date_format = "%Y-%m-%d %H:%M:%S"

    current_qq = None
    is_valid_time = False
    
    lines = file_content.splitlines()
    total_lines = len(lines)
    
    # 进度条
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, line in enumerate(lines):
        # 更新进度条
        if i % 5000 == 0:
            progress = min(i / total_lines, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"正在分析第 {i} 行...")

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
            
            # 简单文本匹配 (可优化为 AC自动机 如果数据量特别大)
            for word, weight in keyword_dict.items():
                if word in line:
                    count = line.count(word)
                    user_scores[current_qq] += count * weight
                    if word not in user_hit_details[current_qq]:
                        user_hit_details[current_qq][word] = 0
                    user_hit_details[current_qq][word] += count
    
    progress_bar.empty()
    status_text.empty()

    # 整理结果
    results = []
    # 动态列名
    score_col_name = f"{index_name}指数"
    
    for qq, score in user_scores.items():
        m_count = msg_counts[qq]
        # 门槛逻辑：分数大于0 且 发言超过10条
        if score > 0 and m_count > 10: 
            # 指数计算公式：(加权分 / 发言总数) * 100
            index = (score / m_count) * 100
            top_word = "无"
            if user_hit_details[qq]:
                top_word = max(user_hit_details[qq], key=user_hit_details[qq].get)
                
            results.append({
                '昵称': user_nicknames[qq],
                'QQ号': qq,
                score_col_name: round(index, 2), # 动态列名
                '加权总分': score,
                '发言总数': m_count,
                '高频词': top_word
            })
    return results, score_col_name

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
    
    if st.button(f"开始分析 ({current_dim_name})", type="primary"):
        with st.spinner(f'正在分析【{current_dim_name}】成分，请稍候...'):
            data, score_col = analyze(content, start_date, end_date, full_dict, current_dim_name)
        
        if data:
            # 转换为 DataFrame
            df = pd.DataFrame(data)
            # 排序
            df = df.sort_values(by=score_col, ascending=False)
            # 生成排名
            df.insert(0, '排名', range(1, len(df) + 1))
            
            # 调整列顺序
            cols = ['排名', '昵称', score_col, '高频词', '加权总分', '发言总数', 'QQ号']
            df = df[cols]
            
            st.success(f"分析完成！基于【{current_dim_name}】维度，找到 {len(df)} 位相关用户。")
            
            # 显示高亮表格
            st.dataframe(
                df, 
                hide_index=True,
                use_container_width=True,
                column_config={
                    score_col: st.column_config.ProgressColumn(
                        score_col,
                        help=f"{current_dim_name}浓度越高，分数越高",
                        format="%.2f",
                        min_value=0,
                        max_value=float(df[score_col].max()) if not df.empty else 100,
                    ),
                }
            )
            
            # 显示图表
            st.subheader(f"📊 {current_dim_name}指数 Top 10")
            if not df.empty:
                top10 = df.head(10).set_index('昵称')
                st.bar_chart(top10[score_col])
            
        else:
            st.warning("未找到符合条件的数据，可能是该群聊中不包含相关关键词。")
