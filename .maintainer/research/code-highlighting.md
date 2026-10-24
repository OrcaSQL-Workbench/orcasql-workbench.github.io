# 页面示例代码语法高亮可行性调研

日期：2026-10-24。仓库审计基线：`34409a412bf2e4e062b2534527f8f11567fde7cc`，不代表已核对远端最新状态。

范围：网站手册中的围栏代码块；不包括复制按钮、行号、编辑器、行内代码高亮或主题重构。本次仅调研，未修改页面实现、依赖或发布流程。

## 结论

**可行，推荐在现有 Python 构建阶段，通过 markdown-it-py 的 `highlight` 回调接入 Pygments，输出带 token class 的静态 HTML，再用局部 CSS 着色。**

这条路径可以保留本站不使用浏览器 JavaScript 的约束，不需要 CDN，不需要改写现有示例正文，也不需要改变 Wiki 镜像内容。仓库固定的 markdown-it-py 4.2.0 已有相应接口，无需为高亮升级 Markdown 解析器。[R1][R2][S1]

当前高亮对象实际集中在 ArkDB 手册：35 个围栏中，33 个是程序、命令或配置，另有 2 个 `text` 输出块。现有语言标记已足够接入，不必逐篇修改文档。ArkTS 示例可以沿用现有 `typescript` 标记进行词法着色，但不能把它称为 ArkTS 编译、语义检查或专用语言支持。

## 当前实现与适用范围

| 检查项 | 当前情况 | 接入含义 |
| --- | --- | --- |
| 内容源与生成器 | Workbench `/docs/`、ArkDB `/arkdb/` 共用 `scripts\build_docs.py`；Markdown 源分别在 `docs`、`docs\arkdb` | 改共享 HTML 渲染能力，而不是手写生成页面。[R1] |
| Markdown 配置 | `MarkdownIt("commonmark", {"html": False}).enable("table")`，未设置 `highlight` | 保留禁用原始 HTML 的设置，仅增加高亮回调。[R1] |
| 代码块 HTML | 当前 SQL 示例为 `<pre><code class="language-sql">…</code></pre>`，内部没有 token span | **只改 CSS 不够**，必须先由词法分析器区分关键字、字符串等内容。 |
| 现有样式 | 只有代码容器背景、横向滚动、等宽字体和 `white-space: pre` | 保留布局，追加限定作用域的 token 样式即可。[R3] |
| 浏览器 JavaScript | 维护约定禁止；站点校验器对任意 `<script>` 直接报错 | 排除直接接入浏览器端高亮脚本的方案。[R2] |
| Wiki | 从原 Markdown 导出，并保护代码块不被链接转换改写 | 仅在网站 HTML 渲染时启用高亮，Wiki 继续输出原围栏。[R4] |
| 发布示例 | 测试按 `token.info == "typescript"` 比对发布包示例原文 | 不改变示例正文、token 内容或现有围栏标记。[R5] |

### 代码块清点

使用现有解析器的 token 对两份手册进行只读清点，结果如下：

| 手册 | 页面 | 围栏代码块 | 缩进代码块 | 行内代码 |
| --- | ---: | ---: | ---: | ---: |
| Workbench | 7 | 0 | 0 | 0 |
| ArkDB | 17 | 35 | 0 | 646 |

ArkDB 围栏分布：`typescript` 28、`powershell` 2、`json5` 2、`sql` 1、`text` 2。当前 35 个围栏均未生成高亮 token span；646 处行内代码不在本次建议范围内。

手册模板没有 CSP meta，不能把隐私页的策略当成整站现有策略。隐私页单独设置了 `default-src 'none'; style-src 'self'`；本次无需调整隐私页或历史归档。[R6]

## 方案比较

| 方案 | 接入方式 | 主要代价或限制 | 判断 |
| --- | --- | --- | --- |
| 只增加 CSS | 使用现有 `language-*` class | 不能区分同一文本节点中的关键字、字符串、注释 | 不满足需求 |
| **Pygments + markdown-it-py** | Python 构建期生成 token HTML 和本地 CSS | 新增固定的 Python 构建依赖；增加 HTML 标记体积 | **推荐，适配现有链路** |
| highlight.js 浏览器端 | 本地托管库、语言定义与 CSS，执行 `highlightAll()` | 自托管不等于无 JavaScript；需要改变仓库约束与校验器 | 不推荐。[S6] |
| Shiki 构建期 | 在构建时生成静态 HTML | 引入额外 JavaScript 构建环境和 Python/JS 交接；默认行内样式需按需调整 | 技术可行，但当前不值得增加这套链路。[S7] |

Pygments 的 `highlight(code, lexer, formatter)` 和 `HtmlFormatter` 可直接用于回调。`nowrap=True` 输出 token 片段，`noclasses=False` 使用 class 而非行内样式，`classprefix` 可隔离 token 类名。[S2]

本次核验的 Pygments 2.21.0 要求 Python ≥3.9，未声明必需的第三方运行时依赖；HTML 高亮不需要可选的终端 `colorama` extra。实施时仍应在 `requirements-docs.txt` 中显式固定经过验证的版本，不能依赖开发机预装包。[S3]

Shiki 不必在浏览器运行，也不能笼统称为必须使用 WASM：它支持不同正则引擎。其官方 `@shikijs/markdown-it` 集成针对 JavaScript `markdown-it`，不是 Python markdown-it-py；核验的 Shiki 4.5.0 要求 Node ≥20。默认行内样式可以用官方转换器提取为 class，但 CSS 收集和输出仍由集成方负责。[S7]

## 推荐接入边界

### 渲染接口与安全降级

markdown-it-py 4.2.0 的围栏渲染器会拆分 info 字符串，以第一个字段为语言，其余作为第三个参数，调用 `highlight(content, lang, attrs)`。回调返回空字符串时使用默认 HTML 转义；返回非空 HTML 片段时则直接使用该结果，通常继续保留原 `<pre><code>` 外壳。[S1]

建议：

- 在 `Documentation.html()` 的渲染器上配置回调，不改变 Markdown 源或 `wiki_markdown()` 的导出行为。
- 使用 `HtmlFormatter(nowrap=True, noclasses=False, classprefix="tok-")`，避免嵌套额外的 `<div><pre>`。
- 使用受控语言映射；`text`、无标记和未知语言返回空字符串，交由 Markdown 渲染器安全转义，不自动猜语言。
- 不把 `attrs` 直接当成任意 formatter 配置或模块路径；真正的库/API/配置错误应使构建明确失败，不做全局异常吞掉后降级。

**`html=False` 不会净化自定义回调的返回值。** 不能把未经转义的原始代码作为成功结果返回。围栏以外的行内代码、缩进代码块有独立渲染规则，本次无需修改。[S1]

### 当前语言的处理

| 源标记 | 建议 lexer 或行为 | 注意事项 |
| --- | --- | --- |
| `typescript` | `TypeScriptLexer` | 保留现有 ArkTS 示例标记；不承诺 ArkTS 专用语义。 |
| `json5` | `Json5Lexer` | 有原生支持，不应当作严格 JSON；该 lexer 自 Pygments 2.19 引入。 |
| `powershell` | `PowerShellLexer` | 覆盖当前命令示例。 |
| `sql` | 建议内部映射到 `MySqlLexer` | 本站当前示例为 MySQL；不必把源围栏改成 `mysql`。若以后文档包含其他方言，再明确区分。 |
| `text`、无标记、未知语言 | 保留纯文本 | 不生成 token span，保留原转义行为。 |

以上 lexer 与别名可由 Pygments 内建映射核对；本次探测环境中查找 `arkts` 没有对应 lexer，不能声称已获得专用 ArkTS 支持。[S4]

### CSS 与文本保持

新增样式应限定在 `.docs-article pre code` 下，例如 `.docs-article pre code .tok-k`，不覆盖当前容器、滚动、字体或打印布局。

**不能把 `HtmlFormatter.get_style_defs(".docs-article pre code")` 的完整输出直接粘贴进共享 CSS。** 本地 Pygments 2.19.2 探测和 2.21.0 源码均显示，其中仍包含全局 `pre` 行高及行号相关规则。应只采用经审查、限定作用域的 token 规则；2.21.0 源码提供了单独生成 token 规则的方法。[S5]

代码文本应以**渲染后代码节点的文本等于原 `token.content`**为硬约束，不比较高亮前后的 HTML 字节。lexer 配置至少明确 `stripnl=False, stripall=False, ensurenl=False, tabsize=0`，避免默认裁剪换行、补换行或展开 tab。[S8]

这些配置不保证所有边界输入都无损：lexer 仍可能处理开头 BOM，formatter 仍可能给未终止的末行补换行。需要覆盖这些案例；无法无损高亮时应明确保持纯文本，而不是改写示例以迁就高亮器。比较基线是解析后的 token，不能误称 Markdown 原始文件字节完全不变。[S8]

### 实施时涉及的文件

| 文件 | 预期变更 |
| --- | --- |
| `requirements-docs.txt` | 固定选定的 Pygments 版本。 |
| `scripts\build_docs.py` | 网站 HTML 渲染增加回调、受控语言映射和明确降级规则。 |
| `site\assets\site.css` | 增加限定在手册代码块内的 token 样式。 |
| `tests\test_docs.py`、`tests\test_arkdb_manual.py` | 覆盖可见 token、文本保持、安全降级及 Wiki/发布示例不变。 |
| `.maintainer\README.md` | 记录构建期高亮及语言、样式维护规则。 |

现有 Pages、Wiki 工作流均已安装 `requirements-docs.txt`，不必仅为增加这一 Python 依赖改造工作流，但两个工作流都需要回归。生成的 `site\docs`、`site\arkdb` 仍不提交，不修改 Wiki 正文。[R2][R7]

## 探索性执行结果与限制

本机预装环境为 Python 3.10.11、markdown-it-py **4.0.0**、Pygments **2.19.2**。未安装新依赖、未写入生成页面，在内存中组合回调与 formatter 后：

- 35 个现有围栏中，33 个非 `text` 块产生 token span，2 个 `text` 块保持纯文本。
- HTMLParser 提取的全部代码文本均与原 `token.content` 相等。
- 5 个合成案例覆盖首尾空行、tab、HTML 特殊字符、伪 `script/img`、中文及未知/无语言，文本保持一致，没有产生真实 script 或行内样式。

这证明接入方向可行，**不等于仓库固定的 markdown-it-py 4.2.0 已完成集成、浏览器或 CI 验收**。4.2.0 的接口已通过其固定版本源码核验，但本次没有执行该版本。

### HTML 体积取舍

在上述同一环境和相同 `commonmark + table` 配置下，比较 ArkDB 17 页正文 HTML 的未压缩 UTF-8 字节：

| 测量项 | 结果 |
| --- | ---: |
| 未高亮正文合计 | 114,313 字节 |
| 高亮后正文合计 | 266,594 字节 |
| 增加 | 152,281 字节 |
| 单页最大增加 | 27,536 字节，`Worker-Integration.md` |

该口径不含导航模板、CSS、HTTP 压缩，也未测浏览器性能，不能代表固定 4.2.0 环境或线上结果。准确取舍是：**增加静态 HTML 和样式，免除客户端高亮脚本及其执行**，不是“零体积开销”，也不能据此保证总体性能更快。

## 实施验收标准与未决项

1. 在仓库固定的 markdown-it-py 4.2.0 与最终选定 Pygments 版本下执行，不依赖开发机预装包。
2. 保留全部现有围栏；当前四类程序/配置语言产生可匹配 CSS 的 token，`text`、未知和无标记内容安全保持纯文本。不能把已有 `language-*` class 当成高亮已生效的证据。
3. 生成 HTML 中的代码文本逐字等于 `token.content`，覆盖中文、实体、反斜杠、tab、首尾空行、BOM 和无末尾换行。
4. `<script>`、`<img onerror=…>` 等代码内容仍只是文本，不出现真实可执行节点、事件属性、行内样式或错误嵌套的代码容器。
5. ArkDB 发布示例原文与 `typescript` 标记保持；Wiki 围栏不混入网页高亮 span；现有单元测试、网站构建和静态校验保持通过。
6. 新样式不外溢到首页、隐私页、打印或行内代码；浏览器中检查配色可读、长行横向滚动和选择复制结果。

实施前需确定最终依赖版本、有限的 token 配色，以及 BOM/无末尾换行等边界输入的无损处理或明确降级策略。以上不影响可行性结论；没有必要为本需求增加浏览器 JavaScript 或第二套构建环境。

## 来源

### 仓库证据

以下均对应本报告开头的仓库基线：

- [R1：共享手册定义与 Markdown/HTML 渲染](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/scripts/build_docs.py#L228-L257)，手册定义见同文件 46–54 行。
- [R2：无 JavaScript 校验](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/scripts/validate_site.py#L83-L84)；[维护约定](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/.maintainer/README.md#L24-L28)及同文件 66、147 行。
- [R3：当前代码容器样式](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/site/assets/site.css#L167-L169)。
- [R4：Wiki 原 Markdown 导出与代码保护](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/scripts/build_docs.py#L259-L313)。
- [R5：发布包示例比对](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/tests/test_arkdb_manual.py#L46-L70)。
- [R6：手册模板](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/scripts/build_docs.py#L346-L400)；[隐私页独立 CSP](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/site/privacy/index.html#L7-L8)。
- [R7：Pages 依赖安装、构建及校验](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/.github/workflows/pages.yml#L93-L117)；[Wiki 依赖安装与测试](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/blob/34409a412bf2e4e062b2534527f8f11567fde7cc/.github/workflows/wiki.yml#L78-L86)。

### 官方资料与固定版本源码

- [S1：markdown-it-py 4.2.0 的围栏回调、降级及外壳](https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/renderer.py#L232-L310)；[HighlightFunc 类型](https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/utils.py#L35-L38)。
- [S2：Pygments 快速入门](https://pygments.org/docs/quickstart/)；[HtmlFormatter 选项](https://pygments.org/docs/formatters/#HtmlFormatter)。
- [S3：Pygments 2.21.0 的 Python 与依赖声明](https://github.com/pygments/pygments/blob/2.21.0/pyproject.toml#L1-L46)。
- [S4：Pygments 2.21.0 内建 lexer 映射](https://github.com/pygments/pygments/blob/2.21.0/pygments/lexers/_mapping.py)；[JSON5 lexer 及引入版本](https://github.com/pygments/pygments/blob/2.21.0/pygments/lexers/json5.py#L34-L46)；[未知别名异常](https://github.com/pygments/pygments/blob/2.21.0/pygments/lexers/__init__.py#L110-L132)。
- [S5：Pygments 2.21.0 样式生成实现](https://github.com/pygments/pygments/blob/2.21.0/pygments/formatters/html.py#L503-L588)；[全局行高的上游测试](https://github.com/pygments/pygments/blob/2.21.0/tests/test_html_formatter.py#L170-L184)。
- [S6：highlight.js 11.12.0 官方浏览器用法](https://github.com/highlightjs/highlight.js/blob/11.12.0/README.md#L74-L107)；[自托管说明](https://github.com/highlightjs/highlight.js/blob/11.12.0/README.md#L443-L451)。
- [S7：Shiki 4.5.0 构建接口](https://github.com/shikijs/shiki/blob/v4.5.0/docs/guide/install.md#L49-L113)；[Node 要求](https://github.com/shikijs/shiki/blob/v4.5.0/packages/shiki/package.json#L42-L67)；[正则引擎](https://github.com/shikijs/shiki/blob/v4.5.0/docs/guide/regex-engines.md#L23-L54)；[JavaScript markdown-it 集成](https://github.com/shikijs/shiki/blob/v4.5.0/packages/markdown-it/src/index.ts#L1-L5)；[样式转 class](https://github.com/shikijs/shiki/blob/v4.5.0/docs/packages/transformers.md#L511-L541)。
- [S8：Pygments Lexer 选项](https://pygments.org/docs/api/#pygments.lexer.Lexer)；[2.21.0 输入预处理](https://github.com/pygments/pygments/blob/2.21.0/pygments/lexer.py#L233-L249)；[HTML 末行处理](https://github.com/pygments/pygments/blob/2.21.0/pygments/formatters/html.py#L896-L911)；[markdown-it-py 4.2.0 输入规范化](https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/rules_core/normalize.py#L12-L19)。

核验的项目本体许可证分别为 [Pygments BSD-2-Clause](https://github.com/pygments/pygments/blob/2.21.0/LICENSE)、[highlight.js BSD-3-Clause](https://github.com/highlightjs/highlight.js/blob/11.12.0/LICENSE)、[Shiki MIT](https://github.com/shikijs/shiki/blob/v4.5.0/LICENSE)。采用库或复制样式资产时应保留相应声明，不把项目本体许可自动推广到所有额外主题资源。
