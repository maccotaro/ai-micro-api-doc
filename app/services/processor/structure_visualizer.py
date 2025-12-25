"""
Document structure visualizer for hierarchical relationships.
文書構造の親子関係を視覚化するためのユーティリティ
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentStructureVisualizer:
    """文書構造の親子関係を様々な形式で視覚化"""
    
    def __init__(self, metadata_path: Path):
        """
        Initialize with document metadata
        
        Args:
            metadata_path: Path to metadata_ext.json
        """
        self.metadata_path = metadata_path
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from JSON file"""
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {}
    
    def generate_hierarchy_tree(self, output_path: Path) -> Path:
        """
        階層構造をツリー形式のテキストファイルで出力
        
        Returns:
            Path to generated tree file
        """
        tree_lines = []
        tree_lines.append(f"📄 {self.metadata.get('document_name', 'Document')}")
        tree_lines.append(f"   Total Pages: {self.metadata.get('total_pages', 0)}")
        tree_lines.append(f"   Total Elements: {self.metadata.get('total_elements', 0)}")
        tree_lines.append("")
        
        # 統一文書構造から階層を抽出
        unified_structure = self.metadata.get('unified_document_structure', {})
        
        if 'sections' in unified_structure:
            tree_lines.append("📚 Document Sections:")
            for section in unified_structure['sections']:
                self._add_section_to_tree(section, tree_lines, indent=1)
        
        # ページ別の詳細構造も表示
        if 'pages' in self.metadata:
            pages_data = self.metadata['pages']
            tree_lines.append("\n📄 Page-by-Page Structure:")
            
            # 最初の5ページの詳細を表示
            for i, page_data in enumerate(pages_data[:5]):
                page_num = page_data.get('page_number', i + 1)
                tree_lines.append(f"   📑 Page {page_num}:")
                
                # 要素数
                elements = page_data.get('elements', [])
                tree_lines.append(f"      Total Elements: {len(elements)}")
                
                # 要素タイプ別統計
                if elements:
                    type_counts = {}
                    for element in elements:
                        element_type = element.get('type', 'unknown')
                        type_counts[element_type] = type_counts.get(element_type, 0) + 1
                    
                    tree_lines.append(f"      Element Types:")
                    for element_type, count in sorted(type_counts.items()):
                        icon = {
                            'title': '📌', 'page_header': '📋', 'page_footer': '🔻', 
                            'text': '📝', 'list_item': '📃', 'table': '📊', 'table_cell': '🔲',
                            'figure': '🖼️', 'caption': '💬', 'footnote': '📎'
                        }.get(element_type, '●')
                        tree_lines.append(f"         {icon} {element_type}: {count}")
                
                # テキスト内容のプレビュー
                text_content = page_data.get('text_content', '')
                if text_content and text_content.strip():
                    preview = text_content[:150] + "..." if len(text_content) > 150 else text_content
                    tree_lines.append(f"      Text Preview: {preview}")
                    
            if len(pages_data) > 5:
                tree_lines.append(f"   ... and {len(pages_data) - 5} more pages")
        
        # 階層アウトラインから構造を抽出
        hierarchical_outline = unified_structure.get('hierarchical_outline', {})
        if 'document_flow' in hierarchical_outline:
            tree_lines.append("\n📊 Document Flow:")
            for flow_item in hierarchical_outline['document_flow']:
                self._add_flow_item_to_tree(flow_item, tree_lines, indent=1)
        
        # DISABLED: File generation - saves storage space
        # tree_file = output_path / "document_structure_tree.txt"
        # with open(tree_file, 'w', encoding='utf-8') as f:
        #     f.write('\n'.join(tree_lines))
        # 
        # logger.info(f"Generated hierarchy tree: {tree_file}")
        # return tree_file
        
        logger.info("Structure tree generation disabled to save storage")
        return None
    
    def _add_section_to_tree(self, section: Dict, lines: List[str], indent: int):
        """セクションをツリーに追加"""
        indent_str = "   " * indent
        section_type = section.get('section_type', 'unknown')
        section_id = section.get('section_id', '')
        
        # セクションタイプに応じたアイコン（Docling実際の要素タイプ）
        icons = {
            'title': '📌',
            'page_header': '📋',
            'page_footer': '🔻',
            'text': '📝',
            'list_item': '📃',
            'table': '📊',
            'table_cell': '🔲',
            'figure': '🖼️',
            'caption': '💬',
            'footnote': '📎'
        }
        icon = icons.get(section_type, '▪️')
        
        # セクション情報
        lines.append(f"{indent_str}{icon} {section_type.upper()}: {section_id}")
        
        # メタデータ
        if 'title' in section:
            lines.append(f"{indent_str}    Title: {section['title']}")
        if 'start_page' in section and 'end_page' in section:
            lines.append(f"{indent_str}    Pages: {section['start_page']}-{section['end_page']}")
        
        # コンテンツ要素の統計を表示
        if 'content_elements' in section:
            content_elements = section['content_elements']
            lines.append(f"{indent_str}    Total Elements: {len(content_elements)}")
            
            # 要素タイプ別の統計
            type_counts = {}
            page_counts = {}
            for element in content_elements:
                element_type = element.get('type', 'unknown')
                page = element.get('source_page', 0)
                
                type_counts[element_type] = type_counts.get(element_type, 0) + 1
                page_counts[page] = page_counts.get(page, 0) + 1
            
            # 要素タイプ別表示
            lines.append(f"{indent_str}    Element Types:")
            for element_type, count in sorted(type_counts.items()):
                type_icon = icons.get(element_type, '●')
                lines.append(f"{indent_str}      {type_icon} {element_type}: {count}")
            
            # ページ別表示（最初の10ページのみ）
            lines.append(f"{indent_str}    Page Distribution:")
            sorted_pages = sorted(page_counts.items())[:10]  # 最初の10ページのみ表示
            for page, count in sorted_pages:
                lines.append(f"{indent_str}      Page {page}: {count} elements")
            if len(page_counts) > 10:
                lines.append(f"{indent_str}      ... and {len(page_counts) - 10} more pages")
            
            # テキストコンテンツのサンプル表示（最初の3つの要素）
            lines.append(f"{indent_str}    Content Preview:")
            for element in content_elements[:3]:
                if element.get('text', '').strip():
                    text_preview = element['text'][:100] + "..." if len(element['text']) > 100 else element['text']
                    lines.append(f"{indent_str}      [{element.get('type', 'unknown')}] {text_preview}")
            if len(content_elements) > 3:
                lines.append(f"{indent_str}      ... and {len(content_elements) - 3} more elements")
        
        # 子要素（サブセクション）
        if 'children' in section:
            for child in section['children']:
                self._add_section_to_tree(child, lines, indent + 1)
        elif 'subsections' in section:
            for subsection in section['subsections']:
                self._add_section_to_tree(subsection, lines, indent + 1)
    
    def _add_flow_item_to_tree(self, flow_item: Dict, lines: List[str], indent: int):
        """フローアイテムをツリーに追加"""
        indent_str = "   " * indent
        sequence = flow_item.get('sequence', 0)
        page = flow_item.get('page', 0)
        element_type = flow_item.get('element_type', 'unknown')
        
        lines.append(f"{indent_str}[{sequence}] Page {page}: {element_type}")
        
        if 'content_preview' in flow_item:
            preview = flow_item['content_preview'][:100] + "..." if len(flow_item.get('content_preview', '')) > 100 else flow_item.get('content_preview', '')
            lines.append(f"{indent_str}    → {preview}")
    
    def generate_html_viewer(self, output_path: Path) -> Path:
        """
        インタラクティブなHTMLビューアーを生成
        
        Returns:
            Path to generated HTML file
        """
        html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Structure Viewer</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #2d3748;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .info-panel {
            background: #f7fafc;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }
        .tree-node {
            margin-left: 20px;
            padding: 5px 0;
            position: relative;
        }
        .tree-node::before {
            content: '';
            position: absolute;
            left: -15px;
            top: 15px;
            width: 10px;
            height: 1px;
            background: #cbd5e0;
        }
        .node-content {
            padding: 8px 15px;
            background: #edf2f7;
            border-radius: 5px;
            margin: 5px 0;
            cursor: pointer;
            transition: all 0.3s ease;
            border-left: 3px solid transparent;
        }
        .node-content:hover {
            background: #e2e8f0;
            border-left-color: #667eea;
            transform: translateX(5px);
        }
        .node-title {
            font-weight: bold;
            color: #2d3748;
        }
        .node-type {
            display: inline-block;
            padding: 2px 8px;
            background: #667eea;
            color: white;
            border-radius: 3px;
            font-size: 12px;
            margin-right: 10px;
        }
        .node-meta {
            font-size: 14px;
            color: #718096;
            margin-top: 5px;
        }
        .collapsible {
            cursor: pointer;
            user-select: none;
        }
        .collapsible::before {
            content: '▼';
            display: inline-block;
            margin-right: 5px;
            transition: transform 0.3s ease;
        }
        .collapsed::before {
            transform: rotate(-90deg);
        }
        .children {
            overflow: visible;
            transition: all 0.3s ease;
            max-height: none;
        }
        .children.hidden {
            display: none;
        }
        .structure-container {
            max-height: 70vh;
            overflow-y: auto;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            background: #f8f9fa;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-card {
            flex: 1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
        }
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 Document Structure Viewer</h1>
        
        <div class="info-panel">
            <strong>Document:</strong> """ + self.metadata.get('document_name', 'Unknown') + """<br>
            <strong>Processing Date:</strong> """ + self.metadata.get('processing_timestamp', 'Unknown') + """<br>
            <strong>Processing Mode:</strong> """ + self.metadata.get('processing_mode', 'Unknown') + """
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">""" + str(self.metadata.get('total_pages', 0)) + """</div>
                <div class="stat-label">Total Pages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">""" + str(self.metadata.get('total_elements', 0)) + """</div>
                <div class="stat-label">Total Elements</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">""" + str(len(self.metadata.get('unified_document_structure', {}).get('sections', []))) + """</div>
                <div class="stat-label">Sections</div>
            </div>
        </div>
        
        <h2>Document Hierarchy</h2>
        <div class="structure-container">
            <div id="structure-tree"></div>
        </div>
    </div>
    
    <script>
        const metadata = """ + json.dumps(self.metadata, ensure_ascii=False, indent=2) + """;
        
        function createTreeNode(data, type = 'section') {
            const node = document.createElement('div');
            node.className = 'tree-node';
            
            const content = document.createElement('div');
            content.className = 'node-content';
            
            // Check for various child structures
            const hasChildren = (data.children && data.children.length > 0) || 
                              (data.subsections && data.subsections.length > 0) || 
                              (data.content_elements && data.content_elements.length > 0);
            
            if (hasChildren) {
                content.className += ' collapsible';
            }
            
            const typeSpan = document.createElement('span');
            typeSpan.className = 'node-type';
            typeSpan.textContent = data.section_type || data.type || type;
            
            const titleSpan = document.createElement('span');
            titleSpan.className = 'node-title';
            
            // Better title generation based on type
            let title = data.title || data.section_id || 'Untitled';
            if (type === 'element') {
                if (data.text && data.text.trim()) {
                    // Show first 100 characters of text content
                    const textPreview = data.text.trim().substring(0, 100);
                    title = textPreview + (data.text.length > 100 ? '...' : '');
                } else {
                    title = `${data.type || 'unknown'} element`;
                }
            }
            titleSpan.textContent = title;
            
            content.appendChild(typeSpan);
            content.appendChild(titleSpan);
            
            // Add metadata
            const metaDiv = document.createElement('div');
            metaDiv.className = 'node-meta';
            let metaText = '';
            
            if (data.start_page && data.end_page) {
                metaText += `Pages: ${data.start_page}-${data.end_page}`;
            } else if (data.source_page) {
                metaText += `Page: ${data.source_page}`;
            }
            
            if (data.content_elements) {
                metaText += ` | Elements: ${data.content_elements.length}`;
                
                // Add element type summary
                const typeCounts = {};
                data.content_elements.forEach(el => {
                    const elType = el.type || 'unknown';
                    typeCounts[elType] = (typeCounts[elType] || 0) + 1;
                });
                
                const typesSummary = Object.entries(typeCounts)
                    .map(([type, count]) => `${type}: ${count}`)
                    .join(', ');
                metaText += ` (${typesSummary})`;
            }
            
            if (metaText) {
                metaDiv.textContent = metaText;
                content.appendChild(metaDiv);
            }
            
            node.appendChild(content);
            
            // Create children containers
            if (hasChildren) {
                const childrenDiv = document.createElement('div');
                childrenDiv.className = 'children';
                
                // Add subsections
                if (data.subsections && data.subsections.length > 0) {
                    data.subsections.forEach(subsection => {
                        childrenDiv.appendChild(createTreeNode(subsection, 'subsection'));
                    });
                }
                
                // Add content elements (show all, but organize by page)
                if (data.content_elements && data.content_elements.length > 0) {
                    // Group elements by page
                    const elementsByPage = {};
                    data.content_elements.forEach(element => {
                        const page = element.source_page || 'unknown';
                        if (!elementsByPage[page]) {
                            elementsByPage[page] = [];
                        }
                        elementsByPage[page].push(element);
                    });
                    
                    // Create page nodes
                    Object.entries(elementsByPage)
                        .sort(([a], [b]) => parseInt(a) - parseInt(b))
                        .forEach(([page, elements]) => {
                            // Create page container
                            const pageNode = document.createElement('div');
                            pageNode.className = 'tree-node';
                            
                            const pageContent = document.createElement('div');
                            pageContent.className = 'node-content collapsible collapsed';
                            
                            const pageTypeSpan = document.createElement('span');
                            pageTypeSpan.className = 'node-type';
                            pageTypeSpan.textContent = 'page';
                            
                            const pageTitleSpan = document.createElement('span');
                            pageTitleSpan.className = 'node-title';
                            pageTitleSpan.textContent = `Page ${page}`;
                            
                            const pageMetaDiv = document.createElement('div');
                            pageMetaDiv.className = 'node-meta';
                            
                            // Count element types for this page
                            const typeCounts = {};
                            elements.forEach(el => {
                                const elType = el.type || 'unknown';
                                typeCounts[elType] = (typeCounts[elType] || 0) + 1;
                            });
                            
                            const typesSummary = Object.entries(typeCounts)
                                .map(([type, count]) => `${type}: ${count}`)
                                .join(', ');
                            pageMetaDiv.textContent = `${elements.length} elements (${typesSummary})`;
                            
                            pageContent.appendChild(pageTypeSpan);
                            pageContent.appendChild(pageTitleSpan);
                            pageContent.appendChild(pageMetaDiv);
                            pageNode.appendChild(pageContent);
                            
                            // Create children for elements
                            const pageChildrenDiv = document.createElement('div');
                            pageChildrenDiv.className = 'children hidden';
                            
                            elements.forEach(element => {
                                pageChildrenDiv.appendChild(createTreeNode(element, 'element'));
                            });
                            
                            pageNode.appendChild(pageChildrenDiv);
                            
                            // Add click handler for page expansion
                            pageContent.addEventListener('click', () => {
                                pageContent.classList.toggle('collapsed');
                                pageChildrenDiv.classList.toggle('hidden');
                            });
                            
                            childrenDiv.appendChild(pageNode);
                        });
                }
                
                // Add regular children
                if (data.children && data.children.length > 0) {
                    data.children.forEach(child => {
                        childrenDiv.appendChild(createTreeNode(child));
                    });
                }
                
                node.appendChild(childrenDiv);
                
                content.addEventListener('click', () => {
                    content.classList.toggle('collapsed');
                    childrenDiv.classList.toggle('hidden');
                });
            }
            
            return node;
        }
        
        function buildTree() {
            const treeContainer = document.getElementById('structure-tree');
            
            // pages_hierarchicalを優先的に使用
            if (metadata.pages_hierarchical && metadata.pages_hierarchical.length > 0) {
                // ページごとのツリーを構築
                metadata.pages_hierarchical.forEach(pageData => {
                    const pageNode = document.createElement('div');
                    pageNode.className = 'tree-node';
                    
                    const pageContent = document.createElement('div');
                    pageContent.className = 'node-content collapsible';
                    
                    const pageTypeSpan = document.createElement('span');
                    pageTypeSpan.className = 'node-type';
                    pageTypeSpan.textContent = 'page';
                    
                    const pageTitleSpan = document.createElement('span');
                    pageTitleSpan.className = 'node-title';
                    // page_numberは既に1ベースなのでそのまま使用
                    pageTitleSpan.textContent = `Page ${pageData.page_number}`;
                    
                    pageContent.appendChild(pageTypeSpan);
                    pageContent.appendChild(pageTitleSpan);
                    
                    // ページ内の要素統計
                    const elements = pageData.logical_ordering || [];
                    if (elements.length > 0) {
                        const metaDiv = document.createElement('div');
                        metaDiv.className = 'node-meta';
                        
                        const typeCounts = {};
                        elements.forEach(elem => {
                            const type = elem.type || 'unknown';
                            typeCounts[type] = (typeCounts[type] || 0) + 1;
                        });
                        
                        const summary = Object.entries(typeCounts)
                            .map(([type, count]) => `${type}: ${count}`)
                            .join(', ');
                        metaDiv.textContent = `${elements.length} elements (${summary})`;
                        pageContent.appendChild(metaDiv);
                    }
                    
                    pageNode.appendChild(pageContent);
                    
                    // 子要素を追加
                    if (elements.length > 0) {
                        const childrenDiv = document.createElement('div');
                        childrenDiv.className = 'children hidden';
                        
                        elements.forEach(element => {
                            childrenDiv.appendChild(createTreeNode(element, 'element'));
                        });
                        
                        pageNode.appendChild(childrenDiv);
                        
                        pageContent.addEventListener('click', () => {
                            pageContent.classList.toggle('collapsed');
                            childrenDiv.classList.toggle('hidden');
                        });
                    }
                    
                    treeContainer.appendChild(pageNode);
                });
            } 
            // フォールバック：従来のsections構造を使用
            else if (metadata.unified_document_structure && metadata.unified_document_structure.sections) {
                metadata.unified_document_structure.sections.forEach(section => {
                    treeContainer.appendChild(createTreeNode(section));
                });
            }
        }
        
        buildTree();
    </script>
</body>
</html>
"""
        
        # DISABLED: HTML viewer file generation - saves storage space
        # html_file = output_path / "document_structure_viewer.html"
        # with open(html_file, 'w', encoding='utf-8') as f:
        #     f.write(html_content)
        # 
        # logger.info(f"Generated HTML viewer: {html_file}")
        # return html_file
        
        logger.info("HTML viewer generation disabled to save storage")
        return None
    
    def generate_mermaid_diagram(self, output_path: Path) -> Path:
        """
        Mermaidダイアグラムで階層構造を表現
        
        Returns:
            Path to generated Mermaid file
        """
        mermaid_lines = ["graph TD"]
        
        # pages_hierarchicalを優先的に使用、なければsectionsにフォールバック
        pages_hierarchical = self.metadata.get('pages_hierarchical', [])
        unified_structure = self.metadata.get('unified_document_structure', {})
        sections = unified_structure.get('sections', [])
        
        # ルートノード
        doc_name = self.metadata.get('document_name', 'Document')
        total_pages = self.metadata.get('total_pages', 0)
        total_elements = self.metadata.get('total_elements', 0)
        mermaid_lines.append(f'    ROOT["📄 {doc_name}<br/>Pages: {total_pages} | Elements: {total_elements}"]')
        
        node_counter = 0
        
        # pages_hierarchicalがある場合はそちらを使用
        if pages_hierarchical:
            # ページグループごとに集計（10ページずつ）
            page_groups = {}
            for page_data in pages_hierarchical:
                page_num = page_data.get('page_number', 0)
                group_id = page_num // 10
                if group_id not in page_groups:
                    page_groups[group_id] = {'pages': [], 'elements': []}
                page_groups[group_id]['pages'].append(page_num)
                
                # logical_orderingから要素を収集
                for elem in page_data.get('logical_ordering', []):
                    page_groups[group_id]['elements'].append(elem)
            
            # グループごとにノードを作成
            for group_id in sorted(page_groups.keys()):
                group_data = page_groups[group_id]
                pages = group_data['pages']
                elements = group_data['elements']
                
                # 要素タイプ別の統計
                type_counts = {}
                for elem in elements:
                    elem_type = elem.get('type', 'unknown')
                    type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
                
                # グループノード
                group_node_id = f"GROUP{node_counter}"
                node_counter += 1
                
                # pagesには既に1ベースのpage_numberが入っている
                page_range = f"Pages {min(pages)}-{max(pages)}" if len(pages) > 1 else f"Page {pages[0]}"
                group_label = f"{page_range}<br/>{len(elements)} elements<br/>"
                
                # 主要な要素タイプを表示
                type_summary = " | ".join([f"{t}:{c}" for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]])
                group_label += type_summary
                
                mermaid_lines.append(f'    {group_node_id}["{group_label}"]')
                mermaid_lines.append(f"    ROOT --> {group_node_id}")
                
                # 各ページの詳細（最初の数ページのみ）
                for page_num in sorted(pages)[:3]:
                    page_node_id = f"P{node_counter}"
                    node_counter += 1
                    
                    # ページ内の要素を収集（page_numは1ベースなので-1してインデックスにする）
                    page_idx = page_num - 1
                    if page_idx < len(pages_hierarchical):
                        page_elements = [e for e in elements if pages_hierarchical[page_idx].get('logical_ordering') and e in pages_hierarchical[page_idx]['logical_ordering']]
                    else:
                        page_elements = []
                    
                    if page_elements:
                        page_type_counts = {}
                        for elem in page_elements:
                            elem_type = elem.get('type', 'unknown')
                            page_type_counts[elem_type] = page_type_counts.get(elem_type, 0) + 1
                        
                        page_stats = f"P{page_num}: "
                        page_stats += " ".join([f"{t}:{c}" for t, c in sorted(page_type_counts.items())])
                        
                        mermaid_lines.append(f'    {page_node_id}("{page_stats}")')
                        mermaid_lines.append(f"    {group_node_id} --> {page_node_id}")
        
        # pages_hierarchicalがない場合は従来のsections処理
        elif sections:
            for section in sections:
                if 'content_elements' in section:
                    # 要素タイプ別の統計を作成
                    type_counts = {}
                    page_set = set()
                    for element in section['content_elements']:
                        element_type = element.get('type', 'unknown')
                        type_counts[element_type] = type_counts.get(element_type, 0) + 1
                        if 'source_page' in element:
                            page_set.add(element['source_page'])
                    
                    # ページ別のサマリーノードを作成
                    node_counter = 0
                    
                    # セクションノード
                    section_title = section.get('title', section.get('section_id', 'Section'))
                    section_node_id = f"SECTION{node_counter}"
                    node_counter += 1
                    
                    # 統計情報を含むノード
                    stats_text = f"{section_title}<br/>Total: {len(section['content_elements'])} elements<br/>"
                    stats_text += "<br/>".join([f"{t}: {c}" for t, c in sorted(type_counts.items())[:5]])
                    if len(type_counts) > 5:
                        stats_text += f"<br/>...and {len(type_counts) - 5} more types"
                    
                    mermaid_lines.append(f'    {section_node_id}["{stats_text}"]')
                    mermaid_lines.append(f"    ROOT --> {section_node_id}")
                    
                    # ページごとのサマリーを作成（全ページ）
                    pages_list = sorted(list(page_set))
                    
                    # ページ数が多い場合は、グループ化して表示
                    if len(pages_list) > 10:
                        # 10ページごとにグループ化
                        for i in range(0, len(pages_list), 10):
                            group_pages = pages_list[i:i+10]
                            group_node_id = f"GROUP{node_counter}"
                            node_counter += 1
                            
                            # グループ内の要素統計
                            group_elements = []
                            for page in group_pages:
                                group_elements.extend([e for e in section['content_elements'] if e.get('source_page') == page])
                            
                            group_type_counts = {}
                            for elem in group_elements:
                                elem_type = elem.get('type', 'unknown')
                                # Doclingの実際の要素タイプをそのまま使用（集約なし）
                                group_type_counts[elem_type] = group_type_counts.get(elem_type, 0) + 1
                            
                            group_label = f"Pages {group_pages[0]}-{group_pages[-1]}<br/>"
                            group_label += f"{len(group_elements)} elements<br/>"
                            type_summary = " | ".join([f"{t}:{c}" for t, c in sorted(group_type_counts.items())[:4]])
                            group_label += type_summary
                            
                            mermaid_lines.append(f'    {group_node_id}["{group_label}"]')
                            mermaid_lines.append(f"    {section_node_id} --> {group_node_id}")
                            
                            # グループ内の各ページ（詳細表示用）
                            for page in group_pages:
                                page_elements = [e for e in section['content_elements'] if e.get('source_page') == page]
                                if page_elements:  # 要素があるページのみ表示
                                    page_node_id = f"P{node_counter}"
                                    node_counter += 1
                                    
                                    # ページ別の要素タイプ統計
                                    page_type_counts = {}
                                    for elem in page_elements:
                                        elem_type = elem.get('type', 'unknown')
                                        # Doclingの実際の要素タイプをそのまま使用（集約なし）
                                        page_type_counts[elem_type] = page_type_counts.get(elem_type, 0) + 1
                                    
                                    page_stats = f"P{page}: "
                                    page_stats += " ".join([f"{t}:{c}" for t, c in sorted(page_type_counts.items())])
                                    
                                    mermaid_lines.append(f'    {page_node_id}("{page_stats}")')
                                    mermaid_lines.append(f"    {group_node_id} --> {page_node_id}")
                    else:
                        # ページ数が少ない場合は直接表示
                        for page in pages_list:
                            page_elements = [e for e in section['content_elements'] if e.get('source_page') == page]
                            if page_elements:  # 要素があるページのみ表示
                                page_node_id = f"PAGE{node_counter}"
                                node_counter += 1
                                
                                # ページ別の要素タイプ統計
                                page_type_counts = {}
                                for elem in page_elements:
                                    elem_type = elem.get('type', 'unknown')
                                    # Doclingの実際の要素タイプをそのまま使用（集約なし）
                                    page_type_counts[elem_type] = page_type_counts.get(elem_type, 0) + 1
                                
                                page_stats = f"Page {page}<br/>{len(page_elements)} elements<br/>"
                                page_stats += " | ".join([f"{t}:{c}" for t, c in sorted(page_type_counts.items())])
                                
                                mermaid_lines.append(f'    {page_node_id}("{page_stats}")')
                                mermaid_lines.append(f"    {section_node_id} --> {page_node_id}")
                else:
                    # シンプルなセクションノード
                    node_counter = self._add_mermaid_nodes(section, mermaid_lines, "ROOT", node_counter)
        
        # DISABLED: Mermaid file generation - saves storage space
        # mermaid_file = output_path / "document_structure.mmd"
        # with open(mermaid_file, 'w', encoding='utf-8') as f:
        #     f.write('\n'.join(mermaid_lines))
        # 
        # # HTML with Mermaid (改良版：スクロール・ズーム対応)
        # html_with_mermaid = output_path / "document_structure_mermaid.html"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Document Structure Diagram</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            padding: 20px;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 20px;
        }}
        .controls {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .controls button {{
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }}
        .controls button:hover {{
            background: #5a67d8;
        }}
        .diagram-container {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 20px rgba(0,0,0,0.2);
            overflow: auto;
            max-height: 80vh;
            position: relative;
        }}
        .mermaid-wrapper {{
            padding: 20px;
            min-width: 1200px;
            transform-origin: top left;
            transition: transform 0.3s ease;
        }}
        .mermaid {{
            font-size: 14px !important;
        }}
        /* Mermaidノードのスタイル調整 */
        .node rect {{
            stroke-width: 2px !important;
        }}
        .node div {{
            padding: 10px !important;
            font-size: 12px !important;
        }}
        .zoom-info {{
            color: #666;
            margin-left: auto;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Document Structure Diagram</h1>
        <div class="controls">
            <button onclick="zoomIn()">🔍 拡大</button>
            <button onclick="zoomOut()">🔍 縮小</button>
            <button onclick="resetZoom()">↺ リセット</button>
            <button onclick="fitToScreen()">⬜ 画面に合わせる</button>
            <span class="zoom-info">Zoom: <span id="zoomLevel">100</span>%</span>
        </div>
        <div class="diagram-container" id="diagramContainer">
            <div class="mermaid-wrapper" id="mermaidWrapper">
                <div class="mermaid" id="mermaidDiagram">
{chr(10).join(mermaid_lines)}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentZoom = 1.0;
        const zoomStep = 0.1;
        const minZoom = 0.3;
        const maxZoom = 3.0;
        
        // Mermaid初期化（改良版設定）
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            flowchart: {{
                useMaxWidth: false,
                htmlLabels: true,
                curve: 'basis',
                nodeSpacing: 50,
                rankSpacing: 80,
                padding: 15
            }},
            fontSize: 14
        }});
        
        function updateZoom() {{
            const wrapper = document.getElementById('mermaidWrapper');
            wrapper.style.transform = `scale(${{currentZoom}})`;
            document.getElementById('zoomLevel').textContent = Math.round(currentZoom * 100);
        }}
        
        function zoomIn() {{
            if (currentZoom < maxZoom) {{
                currentZoom = Math.min(currentZoom + zoomStep, maxZoom);
                updateZoom();
            }}
        }}
        
        function zoomOut() {{
            if (currentZoom > minZoom) {{
                currentZoom = Math.max(currentZoom - zoomStep, minZoom);
                updateZoom();
            }}
        }}
        
        function resetZoom() {{
            currentZoom = 1.0;
            updateZoom();
            document.getElementById('diagramContainer').scrollTop = 0;
            document.getElementById('diagramContainer').scrollLeft = 0;
        }}
        
        function fitToScreen() {{
            const container = document.getElementById('diagramContainer');
            const wrapper = document.getElementById('mermaidWrapper');
            const diagram = document.querySelector('.mermaid svg');
            
            if (diagram) {{
                const containerWidth = container.clientWidth - 40;
                const containerHeight = container.clientHeight - 40;
                const diagramWidth = diagram.getBoundingClientRect().width / currentZoom;
                const diagramHeight = diagram.getBoundingClientRect().height / currentZoom;
                
                const scaleX = containerWidth / diagramWidth;
                const scaleY = containerHeight / diagramHeight;
                currentZoom = Math.min(scaleX, scaleY, 1.0);
                
                updateZoom();
            }}
        }}
        
        // キーボードショートカット
        document.addEventListener('keydown', (e) => {{
            if (e.ctrlKey || e.metaKey) {{
                if (e.key === '=' || e.key === '+') {{
                    e.preventDefault();
                    zoomIn();
                }} else if (e.key === '-') {{
                    e.preventDefault();
                    zoomOut();
                }} else if (e.key === '0') {{
                    e.preventDefault();
                    resetZoom();
                }}
            }}
        }});
        
        // マウスホイールでのズーム
        document.getElementById('diagramContainer').addEventListener('wheel', (e) => {{
            if (e.ctrlKey || e.metaKey) {{
                e.preventDefault();
                if (e.deltaY < 0) {{
                    zoomIn();
                }} else {{
                    zoomOut();
                }}
            }}
        }});
        
        // 初期表示時に画面に合わせる
        window.addEventListener('load', () => {{
            setTimeout(fitToScreen, 500);
        }});
    </script>
</body>
</html>
"""
        
        # DISABLED: HTML with Mermaid file generation - saves storage space  
        # with open(html_with_mermaid, 'w', encoding='utf-8') as f:
        #     f.write(html_content)
        # 
        # logger.info(f"Generated Mermaid diagram: {mermaid_file}")
        # logger.info(f"Generated Mermaid HTML: {html_with_mermaid}")
        # return mermaid_file
        
        logger.info("Mermaid diagram generation disabled to save storage")
        return None
    
    def _add_mermaid_nodes(self, section: Dict, lines: List[str], parent_id: str, counter: int) -> int:
        """Mermaidノードを追加"""
        node_id = f"NODE{counter}"
        counter += 1
        
        section_type = section.get('section_type', 'unknown')
        title = section.get('title', section.get('section_id', 'Untitled'))
        
        # エスケープ処理
        title = title.replace('"', "'").replace('\n', ' ')[:50]
        
        # ノードスタイル
        if section_type == 'title':
            lines.append(f'    {node_id}["{title}"]')
        elif section_type == 'header':
            lines.append(f'    {node_id}("{title}")')
        elif section_type == 'table':
            lines.append(f'    {node_id}[["📊 {title}"]]')
        else:
            lines.append(f'    {node_id}["{title}"]')
        
        # エッジを追加
        lines.append(f"    {parent_id} --> {node_id}")
        
        # 子要素を再帰的に追加
        if 'children' in section:
            for child in section['children']:
                counter = self._add_mermaid_nodes(child, lines, node_id, counter)
        
        return counter