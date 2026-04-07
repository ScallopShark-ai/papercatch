#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模块2：利用 Google Gemini API 自动读取论文 .txt 文件，
用中文总结每篇文章的工作内容、核心问题，并归纳关键词，
输出 YYYY-MM-DD-llm.txt
"""

import json
import os
import re
import sys
import glob
import logging
import time
from datetime import datetime
from openai import OpenAI
import os


def load_config(config_path="config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_keywords_taxonomy(keywords_path="keywords.json"):
    with open(keywords_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("keywords_taxonomy", {})

def find_today_original_file(output_dir):
    """
    查找今天日期的原始论文文件 (YYYY-MM-DD-or-{num}.txt)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    pattern = os.path.join(output_dir, f"{today_str}-or-*.txt")
    files = glob.glob(pattern)
    
    if not files:
        logging.warning(f"未找到今天({today_str})的原始论文文件。")
        return None
    
    # 如果有多个，取最新的
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def parse_papers_from_txt(filepath):
    """
    从原始 .txt 文件中解析出每篇论文的信息
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 用分隔符拆分
    separator_pattern = r"={50}\n={50}"
    blocks = re.split(separator_pattern, content)
    
    papers = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        paper = {}
        
        # 解析各字段
        title_match = re.search(r"论文名称:\s*(.+?)(?:\n\n|\n(?=论文摘要))", block, re.DOTALL)
        summary_match = re.search(r"论文摘要:\s*(.+?)(?:\n\n(?=论文作者)|\n(?=论文作者))", block, re.DOTALL)
        authors_match = re.search(r"论文作者:\s*(.+?)(?:\n\n|\n(?=提交时间))", block, re.DOTALL)
        published_match = re.search(r"提交时间:\s*(.+?)(?:\n\n|\n(?=论文链接))", block, re.DOTALL)
        link_match = re.search(r"论文链接:\s*(.+?)(?:\n|$)", block, re.DOTALL)
        
        paper["title"] = title_match.group(1).strip() if title_match else "未知"
        paper["summary"] = summary_match.group(1).strip() if summary_match else "未知"
        paper["authors"] = authors_match.group(1).strip() if authors_match else "未知"
        paper["published"] = published_match.group(1).strip() if published_match else "未知"
        paper["link"] = link_match.group(1).strip() if link_match else "未知"
        
        papers.append(paper)
    
    return papers

def build_keywords_prompt(taxonomy):
    """
    将关键词分类体系转化为 prompt 的一部分
    """
    lines = []
    for category, terms in taxonomy.items():
        terms_str = ", ".join(terms)
        lines.append(f"  - {category}: [{terms_str}]")
    return "\n".join(lines)

def create_client(config):
    llm_config = config["llm"]
    client = OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],  # https://api.bltcy.ai/v1
    )
    return client

def summarize_paper(client, model, paper, keywords_prompt, max_tokens, temperature, max_retries=5):
    system_instruction = f"""你是一位资深的AI/NLP领域研究助手。你的任务是阅读英文论文摘要，并用中文进行专业、简洁的总结。

请按以下格式输出：

【工作概述】
用2-4句话概括这篇论文做了什么工作，提出了什么方法/框架/模型。

【核心问题】
这篇论文主要解决什么问题？为什么这个问题重要？

【主要贡献】
列出1-3个核心贡献点。

【关键词归类】
根据以下关键词分类体系，为这篇文章匹配最相关的1-3个关键词类别：
{keywords_prompt}

请只输出匹配的类别名称，用顿号分隔。如果都不匹配，请写"其他"。"""

    user_prompt = f"""请分析以下论文：

论文标题: {paper['title']}

论文摘要: {paper['summary']}"""

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait_time = 30 * (attempt + 1)
                logging.warning(f"触发速率限制 (第{attempt+1}次)，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"API调用失败 [{paper['title'][:50]}...]: {e}")
                return f"[总结失败: {error_str}]"
    
    return "[总结失败: 超过最大重试次数]"


def save_summaries(papers, summaries, config):
    """
    将总结结果保存为 YYYY-MM-DD-llm.txt
    """
    output_dir = config.get("output_dir", "./output")
    os.makedirs(output_dir, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today_str}-llm.txt"
    filepath = os.path.join(output_dir, filename)
    
    separator = "=" * 50 + "\n" + "=" * 50
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# arXiv 论文每日总结 - {today_str}\n")
        f.write(f"# 共 {len(papers)} 篇论文\n")
        f.write(f"# 由 Gemini 大模型自动生成\n\n")
        f.write(f"{separator}\n\n")
        
        for i, (paper, summary) in enumerate(zip(papers, summaries)):
            f.write(f"【第 {i+1} 篇】\n\n")
            f.write(f"论文名称: {paper['title']}\n\n")
            f.write(f"论文链接: {paper['link']}\n\n")
            f.write(f"--- Gemini 总结 ---\n\n")
            f.write(f"{summary}\n")
            
            if i < len(papers) - 1:
                f.write(f"\n{separator}\n\n")
    
    logging.info(f"LLM总结已保存至: {filepath}")
    return filepath

def main():
    config = load_config()
    log_level = getattr(logging, config.get("log_level", "INFO"))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logging.info("===== 开始 Gemini 论文总结 =====")
    
    # 周日不分析
    if datetime.now().weekday() == 6:
        logging.info("今天是周日，跳过论文分析。")
        sys.exit(0)
    
    # 查找今天的原始文件
    output_dir = config.get("output_dir", "./output")
    original_file = find_today_original_file(output_dir)
    
    if original_file is None:
        logging.error("找不到今天的原始论文文件，请先运行 fetch_papers.py")
        sys.exit(1)
    
    logging.info(f"读取原始文件: {original_file}")
    
    # 解析论文
    papers = parse_papers_from_txt(original_file)
    logging.info(f"解析出 {len(papers)} 篇论文")
    
    if not papers:
        logging.warning("未解析出任何论文，退出。")
        sys.exit(0)
    
    # 加载关键词分类
    taxonomy = load_keywords_taxonomy()
    keywords_prompt = build_keywords_prompt(taxonomy)
    
    client = create_client(config)

    model = config["llm"].get("model", "gpt-4o-mini")
    max_tokens = config["llm"].get("max_tokens", 4096)
    temperature = config["llm"].get("temperature", 0.3)
    
    # 逐篇总结（带速率控制）
    summaries = []
    for i, paper in enumerate(papers):
        logging.info(f"正在总结第 {i+1}/{len(papers)} 篇: {paper['title'][:60]}...")
        summary = summarize_paper(
            client, model, paper, keywords_prompt, max_tokens, temperature
        )
        summaries.append(summary)
        
        # Gemini 免费版有 RPM 限制，适当间隔避免触发限流
        if i < len(papers) - 1:
            time.sleep(10)
    
    # 保存结果
    filepath = save_summaries(papers, summaries, config)
    logging.info(f"===== Gemini 总结完成，共处理 {len(papers)} 篇论文 =====")
    
    return filepath

if __name__ == "__main__":
    main()
