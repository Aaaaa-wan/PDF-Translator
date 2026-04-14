---
name: en-cap-translator
description: 将自动驾驶法规、安全标准和合规协议从英文翻译为可交付的中英双语 Markdown、DOCX 和印刷版 HTML。适用于 Euro NCAP/ENCAP、UN R79/R157、ISO 26262、SAE J3016、ADAS、自动驾驶测试协议及类似技术/法规文档；尤其适合需要首段提供文档摘要、精确保留标题编号与列表标记、表格和图片不翻译但按原位置保留、术语受控一致的场景。 Use when translating autonomous-driving regulations, safety standards, compliance protocols, Euro NCAP/ENCAP, UN R79/R157, ISO 26262, SAE J3016, ADAS, and similar technical or regulatory documents into bilingual Chinese outputs with a leading summary paragraph and original table/image placement preserved.
---

# 自动驾驶法规双语翻译器

先产出规范的双语 Markdown，再在校验通过后包装为 HTML 或 DOCX。

## 按这个流程执行

1. 在翻译前先把源文档整理成干净的 Markdown 或纯文本。
2. 阅读 [references/translation_guidelines.md](references/translation_guidelines.md) 获取规范输出格式和术语规则。
3. 阅读 [references/chinese-regulatory-style.md](references/chinese-regulatory-style.md) 把中文措辞收敛到法规/协议文体，而不是直译腔。
4. 只有在需要补充法规背景时，才阅读 [references/regulations_overview.md](references/regulations_overview.md)。
5. 先生成整篇文档摘要，并将其作为输出文档的第一段，再按章节翻译为规范双语 Markdown。
6. 运行 `python3 scripts/translate_document.py validate bilingual.md`。
7. 仅在校验通过后，使用 `scripts/generate_html.py` 或 `scripts/generate_docx.py` 打包输出。

## 产出规范双语 Markdown

输出必须保持确定性结构，方便包装脚本稳定解析。

- 输出文档的第一段必须是整篇文档的摘要，采用英文在上、中文在下的双语段落格式。
- 每一条英文标题、段落或列表项，下一行必须紧跟对应中文。
- 英文行和中文行必须保留完全一致的标题编号或列表标记。
- Markdown 表格只保留一份，不翻译单元格内容。
- Markdown 图片、Figure、Table、Annex、公式、代码块以及其他逐字保留内容默认只出现一次；除非用户明确要求双语图题。
- 图片和表格必须按源文档中的原始顺序和相对位置出现在输出文档中，不要在翻译时移动到附录或文末。
- 封面、目录、页眉、页脚默认不翻译，除非用户明确要求保留。
- 打包前必须移除占位内容。`TODO_TRANSLATE` 和 `[ZH: ...]` 都不是有效交付结果。

规范示例：

```md
This document defines the safety and performance boundaries for the steering control function.
本文档定义了转向控制功能的安全边界和性能边界。

1 Scope
1 范围

1.1 Test Conditions
1.1 测试条件

The system shall remain active within the declared operational design domain.
系统应在声明的设计运行域内保持激活。

- The warning shall remain visible.
- 警告应保持可见。
- The driver shall be able to override the function.
- 驾驶员应能够覆盖该功能。

| Parameter | Value |
| --- | --- |
| Speed | 60 km/h |

![Vehicle architecture](images/vehicle-architecture.png)

Figure 2. Test vehicle trajectory
```

## 只在需要时生成翻译工作底稿

文档较长时，可以先生成工作底稿，再分段替换占位内容：

```bash
python3 scripts/translate_document.py skeleton source.md worksheet.md
```

该底稿会自动在最前面插入摘要占位段，保留表格、图片和逐字保留块，并为可翻译内容插入占位符。交付前必须将所有占位符替换为正式内容。

## 打包已校验的结果

生成适合打印或转 PDF 的 HTML：

```bash
python3 scripts/generate_html.py bilingual.md output.html --title "UN R79 bilingual translation"
```

生成无需第三方 Python 包的 DOCX：

```bash
python3 scripts/generate_docx.py bilingual.md output.docx --title "UN R79 bilingual translation"
```

HTML 输出面向浏览器打印或后续转 PDF。如果环境里有专门的 PDF 渲染器，优先渲染生成后的 HTML，而不是重写内容。

## 保持翻译决策稳定

- 严格保留条款编号、要求性关键词和情态动词强度。
- 摘要必须概括文档目标、适用范围、关键约束或测试对象，不要写成泛泛的导语。
- 优先使用术语表中的标准中文术语。如果某个术语没有可靠中文译法，优先保留英文并在上下文中解释一次，不要随意创造松散译名。
- 对规范性或法律性表述采用保守翻译，不为文风而压缩原意。
- 中文应采用法规/标准文体，避免直译腔，例如优先写“可计分”“失效”“充分说明”“不再获准参加”，避免写成“具有得分资格”“不具功能”“有力信息”“不被允许参加”。
- 对定义句优先使用“指”“系指”“用于……”等句式，不要反复堆叠“一种能够……”。
- 对项目名称和协议名称，首次出现时优先保留官方英文名，必要时在中文后补括号说明，例如 `Crash Avoidance（碰撞避免）`。
- 类似 `see Table 3` 的交叉引用应保留在正文中，例如：`see Table 3 (见表 3)`。
- 同一份文档内，同一法规体系的术语必须保持一致。

## 交付前必须校验

运行：

```bash
python3 scripts/translate_document.py validate bilingual.md
```

以下情况会导致校验失败：

- 第一段不是双语摘要
- 可翻译的英文块后面没有紧跟对应中文
- 英文和中文行的标题编号或列表标记不一致
- 文件中仍然存在占位符
- 文件仍在使用过时的 `[ZH: ...]` 占位格式

校验未通过时，不要打包，也不要交付。
