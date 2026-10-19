# OrcaSQL Workbench 文档与网站

本仓库用于维护 OrcaSQL Workbench 的公开用户文档与网站页面，并作为使用问题与文档反馈的统一入口。

## 内容与入口

- **[用户文档（网站）](https://orcasql-workbench.github.io/docs/)**：入门指南、连接与 TLS、SQL 编辑执行、结果导出、历史与文件、常见问题。
- **[用户文档（GitHub Wiki）](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/wiki)**：同一份文档的单向自动同步镜像，首次使用需完成下述初始化和授权。
- **[公开网站（GitHub Pages）](https://orcasql-workbench.github.io/)**：文档导航与问题反馈入口。
- **[隐私政策](https://orcasql-workbench.github.io/privacy/)**：适用于 OrcaSQL Workbench，生效日期为 2026年10月11日。
- **问题反馈（GitHub Issues）**：Workbench 使用问题与文档反馈。

用户文档适用于 0.1.0；当前连接选择器提供 MySQL。相关声明和安装包下载入口尚未发布。

## 单一文档源

只在本仓库的 `docs` 目录维护正文，不直接编辑生成的网站文件或 Wiki。

- `docs\*.md`：用户文档 Markdown，第一行标题与导航标题一致。
- `docs\navigation.json`：网站和 Wiki 共用的页面顺序、标题及网站路径。
- `docs\assets`：两端共用的 PNG、JPEG、WebP 或 SVG 图片。
- `scripts\build_docs.py`：生成网站文档，或导出同样内容到 Wiki。
- `scripts\sync_wiki.py`：使用独立 Wiki 写入凭据，单向同步受管理的文件。

文档内部链接使用源文件名，例如 `Connections.md`；图片使用 `assets/图片名`。发布时转换为网站路径或 Wiki 页面路径。代码块与行内代码不作链接替换，不使用 Wiki 专属的 `[[页面]]` 语法。

生成的 `site\docs` 和 `.build` 不提交 Git。Wiki 镜像会保留自身 Git 历史，但直接修改受管理页面可能被下次同步覆盖；工具不会强制推送，也不会删除未受管理的 Wiki 页面。

## 隐私政策的单一源与应用同步

只在 `privacy\policy-zh-Hans.json` 维护隐私政策正文、标题和生效日期。`scripts\build_privacy.py` 使用 Python 标准库从该源生成网页、应用可读的纯文本和清单，不依赖网络或浏览器；不在应用或 HTML 中另行维护一份政策。

修改后运行：

```powershell
python scripts\build_privacy.py
python scripts\build_privacy.py --check
```

以下生成文件需要与源文件一起提交，不直接编辑：

- `site\privacy\index.html`：当前政策，继续由 `/privacy/` 提供。
- `site\privacy\policy-zh-Hans.txt`：UTF-8、无 BOM、仅 LF 换行，末尾恰好一个换行符；包含完整标题、日期、正文、表格标题与全部单元格、列表，不包含网站导航和重复页脚。
- `site\privacy\manifest.json`：严格包含 `schemaVersion`、`locale`、`effectiveDate`、`policyFile`、`sha256`、`headings` 和 `policyUrl`。`sha256` 对完整 TXT 字节计算，不去除末尾换行；`headings` 按正文顺序包含文档标题及全部 h2/h3。
- `site\privacy\versions\<sha256>\`：同一修订的 HTML、TXT 和清单。`policyUrl` 指向该不可变网页，不指向可变的当前政策入口。

正文段落和标题之间空一行；日期标签与日期值逐行排列；表格标题及列标题逐行排列，每行数据的单元格逐行排列，数据行之间空一行；列表条目逐行排列。源中的行内 HTML 仅支持 `strong`、`code` 和 HTTPS/邮件链接，不引入布局换行。链接在 TXT 中写为 `显示文字 (完整目标地址)`，保留协议、查询参数和片段，因此只修改目标地址也会产生新修订。只有目标恰好是 `mailto:` 加显示邮箱、且不带参数或片段时省略重复地址；当前政策的联系邮箱因此保持原有 TXT 字节和修订。旧版未附带目标地址的归档仍按其原始投影验证，不重写或移除来迁移格式。

生成前执行与应用导入一致的限制：TXT 最多 65,536 个 UTF-8 字节；清单文件（含格式与末尾换行）最多 32,768 字节；标题为 2–64 个非空、唯一、有序的完整段落，每个最多 200 个 UTF-16 代码单元。文档标题必须在首段，最后一个标题后必须有正文，标题不能在其他段落重复出现。TXT 必须是有效 Unicode，无 CR、BOM、U+FFFD、DEL 或禁止的 C0 控制字符，末尾恰好一个 LF；这些限制也检查实体解码后的文本，不新增对 C1 字符的禁令。源字段原有的单行等编写约束仍然适用。任何不兼容的输入都会在写入当前文件或新增归档之前失败，`--check` 同样执行这些限制。

历史修订只新增，不修改或删除。工具检查归档的 TXT 哈希及 HTML、日期、标题和清单的一致性；同一 TXT 修订若对应不同的政策链接或清单，会明确报错而非覆盖。当前页面的非正文调整不会重写已有归档。归档清单从 `HEAD` 的**完整第一父提交历史**重建，将每个归档文件锁定为该历史中首次出现的原始 Git blob；未合并分支不纳入清单，已合并的归档会被纳入。CI 还将 PR 基线或推送前提交的完整第一父历史加入检查，不能因为删除或篡改已经进入 `HEAD`、或者随后有其他提交，就忘记旧修订。完整历史不可用（包括浅克隆）会明确失败；CI 保持 `fetch-depth: 0`，本地浅克隆需先补齐历史。历史修订曾被错误修改或删除时，恢复各文件最初的字节即可重新通过，不必改写失败提交的历史。

`--check` 完全只读，源与生成文件不一致或归档缺失会失败，不会自动修复或发布。`.gitattributes` 固定政策生成文件的 LF，避免 Windows 检出改变校验字节。

应用同步自动化应从**同一个不可变网站 Git 提交**读取 TXT 和清单，并核对清单中的完整字节哈希。网站 Git 提交与 TXT 的 SHA-256 是两个不同的标识；本地尚未提交的预览不能冒用已有提交作为来源。生成文件进入网站提交后才能按该提交下载，归档网址在 Pages 发布后才可访问；本仓库的生成器不会修改应用仓库或发布网站。

## 网站维护与发布

网站使用纯 HTML、CSS 和本地静态资源，没有浏览器端 JavaScript。Markdown 文档使用固定版本的 Python 构建依赖。

- `site\index.html`：文档与支持首页。
- `privacy\policy-zh-Hans.json`：隐私政策唯一编辑源。
- `site\privacy\index.html`：生成的当前隐私政策。
- `site\assets\site.css`：首页与错误页样式。
- `site\assets\privacy.css`：隐私政策页面样式。
- `.github\workflows\pages.yml`：文档构建、静态验证与 GitHub Pages 自动发布。
- `.github\workflows\wiki.yml`：主仓库文档到 GitHub Wiki 的单向同步。

本地检查：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
python scripts\build_privacy.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\build_docs.py --wiki-output .build\wiki
python scripts\validate_site.py
```

本地预览：

```powershell
python -m http.server 4178 --bind 127.0.0.1 --directory site
```

打开 `http://127.0.0.1:4178/`。正式站点使用组织根地址 `https://orcasql-workbench.github.io/`；404 页中的绝对链接从 `/` 开始，与本地预览一致。

PR 构建文档并运行校验；合并到 `main` 后，通过 GitHub Actions 将 `site` 目录发布到 Pages。也可从 `main` 手动运行 `Publish website` 工作流。仓库的 Pages 发布来源应设为 **GitHub Actions**；工作流不会从 PR 或其他分支部署。

## Wiki 初始化与写入授权

GitHub Wiki 使用独立的 `.wiki.git` 仓库，不会直接读取主仓库的 `docs`。

1. 在本仓库的 **Wiki** 页面创建并保存首个 `Home` 首页。临时占位内容会在首次同步时被文档源替换。
2. 准备一个能够写入该公共 Wiki 的专用、有限期令牌。公共 Wiki 通常使用 classic PAT 的 `public_repo` 授权；不要为了此用途授予私有仓库的完整 `repo` 权限，也不要默认认为 Actions 的 `GITHUB_TOKEN` 能写入 Wiki。
3. 在本仓库 **Settings → Secrets and variables → Actions** 中，由凭据持有者直接添加 `WIKI_SYNC_TOKEN`。令牌不得写入代码、文档、命令参数或聊天。
4. 从 `main` 运行 **Sync documentation Wiki**，或通过合并文档更改触发同步。

Wiki 初始化或授权缺失时，同步任务明确失败，不会将“未同步”报告为成功，也不会影响已经独立发布的网站。令牌过期或权限变化时，应在 Actions secrets 中更新后重新运行。

## 问题反馈

如遇到 Workbench 使用问题，或发现文档内容有误、缺漏或过时，请通过 [Issues](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/issues) 反馈。

请说明 Workbench 版本、问题现象和操作步骤。反馈中请勿包含账号凭据、客户数据或其他敏感信息。
