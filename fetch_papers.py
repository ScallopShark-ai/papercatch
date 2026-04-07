#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模块1：从 arXiv 抓取最新论文
根据星期判断检索日期范围，获取论文元数据并写入 .txt 文件
"""

import arxiv
import json
import os
import sys
import logging
import time
from datetime import datetime, timedelta

def load_config(config_path="config.json"):
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_search_date_range(today=None):
    """
    根据今天是星期几，确定要检索的论文日期范围。
    - 周二~周六：检索昨天提交的论文
    - 周一：检索前两天（周六+周日）的论文
    - 周日：不检索，返回 None
    
    返回: (start_date, end_date) 或 None（周日不检索）
    """
    if today is None:
        today = datetime.now()
    
    weekday = today.weekday()  # 0=周一, 6=周日
    
    if weekday == 6:  # 周日
        logging.info("今天是周日，不检索论文。")
        return None
    elif weekday == 0:  # 周一
        start_date = today - timedelta(days=2)  # 周六
        end_date = today - timedelta(days=1)    # 周日
    else:  # 周二~周六
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
    
    return (start_date, end_date)
# def get_search_date_range(today=None):
#     """
#     测试版本：固定检索 2026-04-01 ~ 2026-04-04 的论文
#     """
#     start_date = datetime(2026, 4, 1)
#     end_date = datetime(2026, 4, 4)
#     logging.info(f"[测试模式] 固定检索日期: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
#     return (start_date, end_date)


def build_query(config, start_date, end_date):
    """
    构建 arXiv 查询字符串。
    结合分类和关键词进行检索，同时用 submittedDate 做日期过滤。
    """
    # 日期格式化为 arXiv API 所需格式: YYYYMMDDHHMMSS
    date_start = start_date.strftime("%Y%m%d") + "0000"
    date_end = end_date.strftime("%Y%m%d") + "2359"
    
    # 构建分类查询
    categories = config["arxiv"]["search_queries"]
    cat_query = " OR ".join(categories)
    
    # 构建关键词查询
    keywords = config["arxiv"]["keywords"]
    if keywords:
        kw_parts = []
        for kw in keywords:
            kw_parts.append(f'all:"{kw}"')
        kw_query = " OR ".join(kw_parts)
        # 分类 AND (关键词)
        search_query = f"({cat_query}) AND ({kw_query}) AND submittedDate:[{date_start} TO {date_end}]"
    else:
        search_query = f"({cat_query}) AND submittedDate:[{date_start} TO {date_end}]"
    
    return search_query

def fetch_papers(config):
    today = datetime.now()
    date_range = get_search_date_range(today)

    if date_range is None:
        return None, 0

    start_date, end_date = date_range
    logging.info(f"检索日期范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")

    date_start = start_date.strftime("%Y%m%d") + "0000"
    date_end = end_date.strftime("%Y%m%d") + "2359"

    categories = config["arxiv"]["search_queries"]
    cat_query = " OR ".join(categories)

    keywords = config["arxiv"].get("keywords", [])
    max_results = config["arxiv"].get("max_results", 100)

    client = arxiv.Client(
        page_size=100,
        delay_seconds=5.0,
        num_retries=5
    )

    # 用论文链接做去重
    seen_ids = set()
    papers = []

    for kw in keywords:
        query = f'({cat_query}) AND all:"{kw}" AND submittedDate:[{date_start} TO {date_end}]'
        logging.info(f"正在检索关键词: {kw}")

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        try:
            for result in client.results(search):
                # 用论文ID去重，避免同一篇被多个关键词重复抓到
                if result.entry_id in seen_ids:
                    continue
                seen_ids.add(result.entry_id)

                paper = {
                    "title": result.title,
                    "summary": result.summary,
                    "authors": ", ".join([author.name for author in result.authors]),
                    "published": result.published.strftime("%Y-%m-%d %H:%M:%S"),
                    "link": result.entry_id
                }
                papers.append(paper)
        except Exception as e:
            logging.warning(f"关键词 '{kw}' 检索失败: {e}，跳过继续...")
            time.sleep(10)
            continue

        logging.info(f"关键词 '{kw}' 完成，当前累计 {len(papers)} 篇")
        # 每个关键词查完等 3 秒，避免触发 arxiv 速率限制
        time.sleep(3)

    logging.info(f"共检索到 {len(papers)} 篇论文（去重后）")
    return papers, len(papers)


def save_papers_to_txt(papers, config, paper_count):
    """
    将论文信息保存为 .txt 文件
    格式: YYYY-MM-DD-or-{num}.txt
    """
    output_dir = config.get("output_dir", "./output")
    os.makedirs(output_dir, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today_str}-or-{paper_count}.txt"
    filepath = os.path.join(output_dir, filename)
    
    separator = "=" * 50 + "\n" + "=" * 50
    
    with open(filepath, "w", encoding="utf-8") as f:
        for i, paper in enumerate(papers):
            f.write(f"论文名称: {paper['title']}\n\n")
            f.write(f"论文摘要: {paper['summary']}\n\n")
            f.write(f"论文作者: {paper['authors']}\n\n")
            f.write(f"提交时间: {paper['published']}\n\n")
            f.write(f"论文链接: {paper['link']}\n")
            
            if i < len(papers) - 1:
                f.write(f"\n{separator}\n\n")
    
    logging.info(f"论文信息已保存至: {filepath}")
    return filepath

def main():
    # 设置日志
    config = load_config()
    log_level = getattr(logging, config.get("log_level", "INFO"))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logging.info("===== 开始抓取 arXiv 论文 =====")
    
    # 检查是否是周日
    if datetime.now().weekday() == 6:
        logging.info("今天是周日，跳过论文抓取。")
        sys.exit(0)
    
    papers, count = fetch_papers(config)
    
    if papers is None or count == 0:
        logging.warning("未检索到任何论文，程序退出。")
        sys.exit(0)
    
    filepath = save_papers_to_txt(papers, config, count)
    logging.info(f"===== 抓取完成，共 {count} 篇论文 =====")
    
    return filepath

if __name__ == "__main__":
    main()
