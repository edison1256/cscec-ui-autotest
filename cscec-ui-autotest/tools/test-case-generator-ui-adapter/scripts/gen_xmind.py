#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用XMind生成器 - 从Markdown树结构生成XMind思维导图文件

用法（Windows）:
    py -3 gen_xmind.py --input "大纲.md" --output "输出.xmind" --title "中心主题"

用法（已配置 python 命令时）:
    python gen_xmind.py --input "大纲.md" --output "输出.xmind" --title "中心主题"

支持的Markdown格式:
    1. 标题层级：# 一级  ## 二级  ### 三级
    2. 缩进列表：- 一级\n  - 二级\n    - 三级
    3. 树形符号：├── 一级\n│   ├── 二级\n└── 三级
    4. 混合使用（自动检测并使用最佳解析器）

树形符号格式说明:
    ├── 表示同级节点
    └── 表示末尾同级节点
    │   表示父级延续线
    缩进层级由这些符号的位置决定
"""

import argparse
import re
import uuid
import zipfile
import os
import sys
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def gen_id():
    """生成XMind格式的ID"""
    return uuid.uuid4().hex.upper()


def get_timestamp():
    """获取当前时间戳（毫秒）"""
    return str(int(datetime.now().timestamp() * 1000))


def create_topic(parent_xml, title_text, children_data=None):
    """创建一个topic节点"""
    topic = SubElement(parent_xml, 'topic')
    topic.set('id', gen_id())
    topic.set('timestamp', get_timestamp())
    
    title = SubElement(topic, 'title')
    title.text = title_text
    
    if children_data:
        children = SubElement(topic, 'children')
        topics_attached = SubElement(children, 'topics')
        topics_attached.set('type', 'attached')
        
        for child_title, child_children in children_data:
            create_topic(topics_attached, child_title, child_children if child_children else None)
    
    return topic


# ============================================================================
# 多格式Markdown解析器
# ============================================================================

def detect_format(lines):
    """
    检测Markdown内容的主要格式类型
    
    返回: 'tree' | 'heading' | 'list' | 'plain'
    """
    tree_count = 0
    heading_count = 0
    list_count = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == '---' or stripped.startswith('>'):
            continue
        # 跳过代码块标记
        if stripped.startswith('```'):
            continue
        # 跳过表格行
        if stripped.startswith('|'):
            continue
        
        # 检测树形符号
        if re.search(r'[├└│─┬┴┼]', stripped):
            tree_count += 1
        # 检测标题
        elif re.match(r'^#{1,6}\s', stripped):
            heading_count += 1
        # 检测列表
        elif re.match(r'^(\s*)([-*]|\d+\.)\s', stripped):
            list_count += 1
    
    if tree_count >= 3:
        return 'tree'
    elif heading_count >= 2:
        return 'heading'
    elif list_count >= 3:
        return 'list'
    else:
        # 混合场景：优先使用树形
        if tree_count > 0:
            return 'tree'
        elif heading_count > 0:
            return 'heading'
        elif list_count > 0:
            return 'list'
        return 'plain'


def parse_markdown_tree(md_content):
    """
    解析Markdown内容为树结构，自动检测格式
    
    支持的混合格式：
    - 标题（### M1:xxx）+ 代码块内的树形结构（├── └──）
    - 纯标题层级
    - 纯列表
    - 纯树形符号
    
    返回格式: [(title, children), ...]
    children格式同上（递归）
    """
    lines = md_content.strip().split('\n')
    
    # === 第一步：分段处理 ===
    # 将文档按标题分成段，每段可能包含：标题行 + 代码块(树形) + 列表 + 表格等
    sections = []  # [(heading_text, content_lines), ...]
    current_heading = None
    current_lines = []
    in_code_block = False
    code_block_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # 处理代码块边界
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
                current_lines.extend(code_block_lines)
                code_block_lines = []
            else:
                in_code_block = True
            continue
        
        if in_code_block:
            code_block_lines.append(line)
            continue
        
        # 跳过空行/分隔线/引用/表格分隔行
        if not stripped or stripped == '---' or stripped.startswith('>'):
            continue
        if re.match(r'^\|[-:\s|]+\|$', stripped):
            continue
        
        # 检测标题行（作为分段标记）
        heading_match = re.match(r'^#{1,6}\s+(.+)$', stripped)
        
        # 对于大纲文档，只用二三级标题作为分段标记
        # 一级标题(#)通常是文档标题，跳过
        if heading_match and not stripped.startswith('# '):
            heading_level = len(stripped.split()[0])  # #的数量
            heading_text = heading_match.group(1).strip()
            
            # 保存之前的段
            if current_heading is not None or current_lines:
                sections.append((current_heading, current_lines))
            
            current_heading = heading_text
            current_lines = []
        else:
            # 非标题行加入当前段
            # 跳过表格数据行（大纲中的表格不属于树形结构）
            if stripped.startswith('|') and not re.search(r'[├└│─┬┴┼]', stripped):
                continue
            current_lines.append(line)
    
    # 保存最后一段
    if current_heading is not None or current_lines:
        sections.append((current_heading, current_lines))
    
    if not sections:
        # 没有分段信息，回退到整体解析
        return _parse_flat_content(lines)
    
    # === 第二步：逐段解析 ===
    result = []
    
    for heading_text, content_lines in sections:
        # 过滤有效行
        valid_lines = []
        for line in content_lines:
            stripped = line.strip()
            if not stripped:
                continue
            valid_lines.append(line)
        
        if heading_text and valid_lines:
            # 有标题有内容：标题作为父节点，内容解析为子节点
            children = _parse_content_lines(valid_lines)
            result.append((heading_text, children))
        elif heading_text:
            # 只有标题没有内容
            result.append((heading_text, []))
        else:
            # 没有标题只有内容
            children = _parse_content_lines(valid_lines)
            result.extend(children)
    
    return result


def _parse_content_lines(lines):
    """解析一组内容行，自动选择最佳解析器"""
    if not lines:
        return []
    
    # 检测格式
    fmt = detect_format(lines)
    
    if fmt == 'tree':
        return parse_by_tree_symbols(lines)
    elif fmt == 'heading':
        return parse_by_headings(lines)
    elif fmt == 'list':
        return parse_by_list(lines)
    else:
        return [(line.strip(), None) for line in lines if line.strip()]


def _parse_flat_content(lines):
    """回退：整体解析（无分段标题时）"""
    meaningful_lines = []
    in_code_block = False
    code_block_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
                for cb_line in code_block_lines:
                    meaningful_lines.append(cb_line)
                code_block_lines = []
            else:
                in_code_block = True
            continue
        
        if in_code_block:
            code_block_lines.append(line)
            continue
        
        if not stripped or stripped == '---' or stripped.startswith('>'):
            continue
        if re.match(r'^\|[-:\s|]+\|$', stripped):
            continue
        
        meaningful_lines.append(line)
    
    if not meaningful_lines:
        return []
    
    fmt = detect_format(meaningful_lines)
    
    if fmt == 'tree':
        return parse_by_tree_symbols(meaningful_lines)
    elif fmt == 'heading':
        return parse_by_headings(meaningful_lines)
    elif fmt == 'list':
        return parse_by_list(meaningful_lines)
    else:
        return [(line.strip(), None) for line in meaningful_lines if line.strip()]


def parse_by_tree_symbols(lines):
    """
    按树形符号层级解析（├── └── │）
    
    树形格式的层级由符号位置决定：
    - ├── 或 └── 表示一个同级或子级节点
    - │   表示父级延续线
    - 每一层的缩进通常是4个字符（├── 或 └── 占3字符+1空格）
    
    算法：
    1. 识别每个节点的深度（通过├/└出现的位置）
    2. 构建树结构
    """
    # 预处理：提取每个树节点的文本和层级
    nodes = []  # [(depth, text), ...]
    
    for line in lines:
        stripped = line.strip()
        
        # 查找 ├── 或 └── 标记的位置
        match = re.search(r'[├└]──\s*(.+)', stripped)
        if not match:
            # 也支持 ┬── 格式
            match = re.search(r'┬──\s*(.+)', stripped)
        if not match:
            continue
        
        text = match.group(1).strip()
        if not text:
            continue
        
        # 计算深度：通过├/└前面的字符位置
        # 找到├或└的字符位置
        symbol_pos = -1
        for i, ch in enumerate(stripped):
            if ch in '├└┬':
                symbol_pos = i
                break
        
        # 深度 = 位置 / 4（每4个字符一层：│ + 空格 + 空格 + 空格 或 ├── + 空格）
        # 实际上标准树形格式：第一层├在位置0，第二层├在位置4，以此类推
        if symbol_pos == 0:
            depth = 0
        else:
            # 计算前面有多少个层级指示符
            prefix = stripped[:symbol_pos]
            # 每个"│   "或"    "代表一层
            depth = 0
            i = 0
            while i < len(prefix):
                if prefix[i] == '│':
                    depth += 1
                    i += 4  # 跳过 "│   "
                elif prefix[i] == ' ':
                    depth += 1
                    i += 4  # 跳过 "    "
                else:
                    i += 1
        
        nodes.append((depth, text))
    
    if not nodes:
        return []
    
    # 构建树结构
    return _build_tree_from_nodes(nodes)


def _build_tree_from_nodes(nodes):
    """
    从扁平的(depth, text)节点列表构建树结构
    
    算法：使用栈维护当前路径
    """
    if not nodes:
        return []
    
    root_items = []
    stack = []  # [(depth, node)]
    
    for depth, text in nodes:
        node = (text, [])
        
        # 弹出栈中depth >= 当前depth的项
        while stack and stack[-1][0] >= depth:
            stack.pop()
        
        if stack:
            # 添加为父节点的子节点
            stack[-1][1][1].append(node)
        else:
            root_items.append(node)
        
        stack.append((depth, node))
    
    return root_items


def parse_by_headings(lines):
    """按标题层级解析"""
    root_items = []
    stack = []  # [(level, node)]
    
    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if not heading_match:
            # 非标题行，尝试作为列表项处理
            list_match = re.match(r'^(\s*)([-*]|\d+\.)\s+(.+)$', line)
            if list_match:
                text = list_match.group(3).strip()
                if stack:
                    parent_level, parent_node = stack[-1]
                    child_item = (text, [])
                    parent_node[1].append(child_item)
            continue
        
        level = len(heading_match.group(1))
        text = heading_match.group(2).strip()
        node = (text, [])
        
        # 弹出栈中level >= 当前level的项
        while stack and stack[-1][0] >= level:
            stack.pop()
        
        if stack:
            stack[-1][1][1].append(node)
        else:
            root_items.append(node)
        
        stack.append((level, node))
    
    return root_items


def parse_by_list(lines):
    """按列表缩进层级解析"""
    root_items = []
    stack = []  # [(indent, node)]
    
    for line in lines:
        list_match = re.match(r'^(\s*)([-*]|\d+\.)\s+(.+)$', line)
        if not list_match:
            continue
        
        indent = len(list_match.group(1))
        text = list_match.group(3).strip()
        node = (text, [])
        
        # 弹出栈中indent >= 当前indent的项
        while stack and stack[-1][0] >= indent:
            stack.pop()
        
        if stack:
            stack[-1][1][1].append(node)
        else:
            root_items.append(node)
        
        stack.append((indent, node))
    
    return root_items


# ============================================================================
# XMind XML构建
# ============================================================================

def build_xmind_from_tree(tree_data, center_title):
    """从树结构数据构建XMind content.xml"""
    xmap = Element('xmap-content')
    xmap.set('xmlns', 'urn:xmind:xmap:xmlns:content:2.0')
    xmap.set('xmlns:fo', 'http://www.w3.org/1999/XSL/Format')
    xmap.set('xmlns:svg', 'http://www.w3.org/2000/svg')
    xmap.set('xmlns:xhtml', 'http://www.w3.org/1999/xhtml')
    xmap.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
    xmap.set('timestamp', get_timestamp())
    xmap.set('version', '2.0')
    
    # Sheet
    sheet = SubElement(xmap, 'sheet')
    sheet.set('id', gen_id())
    sheet.set('timestamp', get_timestamp())
    
    # 中心主题
    center_topic = SubElement(sheet, 'topic')
    center_topic.set('id', gen_id())
    center_topic.set('timestamp', get_timestamp())
    center_topic.set('structure-class', 'org.xmind.ui.map.unbalanced')
    
    title = SubElement(center_topic, 'title')
    title.text = center_title
    
    if tree_data:
        children = SubElement(center_topic, 'children')
        topics_attached = SubElement(children, 'topics')
        topics_attached.set('type', 'attached')
        
        for child_title, child_children in tree_data:
            create_topic(topics_attached, child_title, child_children if child_children else None)
    
    # Sheet title
    sheet_title = SubElement(sheet, 'title')
    sheet_title.text = '测试大纲'
    
    return xmap


def build_meta_xml():
    """构建meta.xml"""
    meta = Element('meta')
    meta.set('xmlns', 'urn:xmind:xmap:xmlns:meta:2.0')
    
    SubElement(meta, 'Author').text = 'TestArchitect'
    SubElement(meta, 'Create').text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    SubElement(meta, 'Version').text = '3.7.0'
    
    return meta


def build_manifest_xml():
    """构建manifest.xml"""
    manifest = Element('manifest')
    manifest.set('xmlns', 'urn:xmind:xmap:xmlns:manifest:1.0')
    
    entry1 = SubElement(manifest, 'file-entry')
    entry1.set('entry', 'META-INF/')
    entry1.set('media-type', '')
    
    entry2 = SubElement(manifest, 'file-entry')
    entry2.set('entry', 'content.xml')
    entry2.set('media-type', 'text/xml')
    
    entry3 = SubElement(manifest, 'file-entry')
    entry3.set('entry', 'meta.xml')
    entry3.set('media-type', 'text/xml')
    
    entry4 = SubElement(manifest, 'file-entry')
    entry4.set('entry', 'manifest.xml')
    entry4.set('media-type', 'text/xml')
    
    return manifest


def xml_to_string(elem):
    """将Element转换为格式化的XML字符串"""
    rough_string = tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toxml(encoding='utf-8').decode('utf-8')


def count_nodes(tree_data):
    """统计树中的节点数"""
    count = 0
    for title, children in tree_data:
        count += 1
        if children:
            count += count_nodes(children)
    return count


def max_depth(tree_data, current_depth=1):
    """计算树的最大深度"""
    if not tree_data:
        return current_depth
    max_d = current_depth
    for title, children in tree_data:
        if children:
            d = max_depth(children, current_depth + 1)
            max_d = max(max_d, d)
    return max_d


def create_xmind(md_content, output_path, center_title):
    """从Markdown内容创建XMind文件"""
    # 解析Markdown为树结构
    tree_data = parse_markdown_tree(md_content)
    
    if not tree_data:
        print("警告：未解析到有效的树结构数据，将生成空思维导图")
        tree_data = [("（无数据）", None)]
    
    # 统计信息
    node_count = count_nodes(tree_data)
    depth = max_depth(tree_data)
    
    # 构建XMind XML
    content_xml = build_xmind_from_tree(tree_data, center_title)
    meta_xml = build_meta_xml()
    manifest_xml = build_manifest_xml()
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 写入ZIP文件
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('content.xml', xml_to_string(content_xml))
        zf.writestr('meta.xml', xml_to_string(meta_xml))
        zf.writestr('META-INF/manifest.xml', xml_to_string(manifest_xml))
    
    print(f'XMind文件已生成: {output_path}')
    print(f'   一级分支数: {len(tree_data)}')
    print(f'   总节点数: {node_count}')
    print(f'   最大深度: {depth}')
    return output_path


def main():
    parser = argparse.ArgumentParser(description='从Markdown大纲生成XMind思维导图')
    parser.add_argument('--input', '-i', required=True, help='输入的Markdown文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出的XMind文件路径')
    parser.add_argument('--title', '-t', default='测试大纲', help='中心主题标题（默认：测试大纲）')
    parser.add_argument('--debug', '-d', action='store_true', help='调试模式：输出解析的树结构')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"错误：输入文件不存在: {args.input}")
        sys.exit(1)
    
    with open(args.input, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    if args.debug:
        tree_data = parse_markdown_tree(md_content)
        print("=== 解析结果 ===")
        _print_tree(tree_data)
        print(f"\n一级分支: {len(tree_data)}")
        print(f"总节点数: {count_nodes(tree_data)}")
        print(f"最大深度: {max_depth(tree_data)}")
    else:
        create_xmind(md_content, args.output, args.title)


def _print_tree(tree_data, indent=0):
    """调试用：打印树结构"""
    for title, children in tree_data:
        print(f"{'  ' * indent}- {title}")
        if children:
            _print_tree(children, indent + 1)


if __name__ == '__main__':
    main()
