# 维护者手册

## 修改文档

用户文档和开发者手册放在 `docs` 目录。网站和 Wiki 都从这里生成，修改内容时只改对应的 Markdown 和导航，不另行维护 Wiki 正文。

| 手册 | 唯一内容源 | 网站入口 | Wiki 目标 |
| --- | --- | --- | --- |
| Workbench 用户文档 | `docs\*.md`、`docs\navigation.json` | `/docs/` | 本仓库的 Wiki |
| ArkDB 开发者手册 | `docs\arkdb\*.md`、`docs\arkdb\navigation.json` | `/arkdb/` | `OrcaSQL-Workbench/ArkDB` 的 Wiki |

- `docs\*.md`：文档正文。第一行标题要与导航中的标题一致。
- `docs\navigation.json`：页面顺序、标题和网站路径，网站与 Wiki 共用。
- `docs\assets`：文档图片，支持 PNG、JPEG、WebP 和 SVG。

ArkDB 手册使用同样的文件和导航规则，图片放在 `docs\arkdb\assets`。链接只引用同一手册内的源文件名；跨手册使用完整的网站 HTTPS 地址。`scripts\build_docs.py` 中的 `MANUALS` 固定每份手册的源目录、网站路径和 Wiki 仓库，Wiki 同步不接受任意远端地址。

ArkDB 导航使用 `version: 2`。每页在 `source`、`slug`、`title` 之外填写 `section`，网站目录和 Wiki 侧栏会按分组显示。同组页面按清单中的先后顺序排列。`nav: false` 只隐藏目录项，页面仍会生成，供旧链接使用；首页不能隐藏。Workbench 继续使用原有的 `version: 1` 平铺目录。

移动章节时保留旧页面的标题、路径和原有章节标题，在原位置放上简短说明和新页面链接。Wiki 文件名来自页面标题，改标题也会改变 Wiki 链接。页面内的目录直接写 Markdown 锚点链接，网站检查会核对目标是否存在。

文档之间的链接直接写源文件名，例如 `Connections.md`；图片路径写成 `assets/图片名`。发布时，脚本会转换为网站或 Wiki 对应的链接。代码块和行内代码中的内容不会转换。

不要使用 Wiki 专属的 `[[页面]]` 链接语法，也不要直接修改生成的 `site\docs`、`site\arkdb` 或 Wiki 页面，以免被下次同步覆盖。

用户指南不标注固定的适用版本，但要写清楚当前支持的功能。反馈问题时，仍需提供实际使用的 Workbench 版本。

`site\docs`、`site\arkdb` 和 `.build` 都是生成内容，不提交 Git。

ArkDB 的接口与支持边界应对照上游公共 `mysql\Index.ets`、包指南和实际 Release 更新。下载示例可固定到真实发布的版本，但不要把工程预览写成生产认证，或把尚未实现的驱动、参数绑定、连接池和托管 Worker 写成可用功能。

当前手册以 MySQL 1.0.2 为准。`tests\fixtures\arkdb-mysql-1.0.2-examples.json` 保存从实际发布 HAR 提取的八个包指南示例，以及 HAR、包指南摘要和源码提交。`test_arkdb_manual.py` 比对手册中的 ArkTS 示例，并检查旧页面、章节链接和站内导航。更新示例时先核对对应发行包，不把仅存在于开发分支的接口写进已发布版本的用法。

## 隐私政策的单一源与应用同步

只在 `privacy\policy-zh-Hans.json` 维护隐私政策正文、标题和生效日期。`scripts\build_privacy.py` 使用 Python 标准库从该源生成网页、应用可读的纯文本和清单，不依赖网络或浏览器；不在应用或 HTML 中另行维护一份政策。

修改后在仓库根目录运行：

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

## 修改网站

网站使用 HTML、CSS 和本地静态资源，不使用浏览器端 JavaScript。

- `site\index.html`：网站首页。
- `privacy\policy-zh-Hans.json`：隐私政策唯一编辑源。
- `site\privacy\index.html`：生成的当前隐私政策。
- `site\assets\site.css`：首页和错误页样式。
- `site\assets\privacy.css`：隐私政策页面样式。

正式地址是 `https://orcasql-workbench.github.io/`。网站部署在组织根路径 `/`，不是仓库名下面。站内绝对链接从 `/` 开始，404 页的资源链接和返回首页链接也一样。

## 本地检查

在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
python scripts\build_privacy.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\build_docs.py --wiki-output .build\wiki
python scripts\validate_site.py
```

`build_docs.py` 负责生成网站文档和导出 Wiki 文件，`validate_site.py` 负责检查静态页面。

默认构建两份手册；上面的 Wiki 导出分别写入 `.build\wiki\workbench` 和 `.build\wiki\arkdb`，各有独立的 `Home`、目录、页脚和管理清单。只构建或导出 ArkDB 时使用：

```powershell
python scripts\build_docs.py --manual arkdb --wiki-output .build\wiki\arkdb
```

`--manual workbench` 选择用户文档。`--source` 和 `--site-output` 可覆盖单份手册的输入输出，不能与 `--manual all` 混用。Wiki 导出不需要令牌，不会写远端。

## 本地预览

构建完成后，在仓库根目录启动预览：

```powershell
python -m http.server 4178 --bind 127.0.0.1 --directory site
```

打开 `http://127.0.0.1:4178/`。

## 发布网站

仓库的 Pages 发布来源要设为 **GitHub Actions**。

涉及网站或文档的 PR 会运行构建和检查。合并到 `main` 后，`Publish website` 工作流会自动发布 `site` 目录。需要重新发布时，也可以从 `main` 手动运行。

工作流文件是 `.github\workflows\pages.yml`，只发布 `main` 分支的内容。

## Actions 运行标题与任务名称

运行标题区分来源、阶段和目标，发布触发方式不变：

- PR 新建或更新：`PR #100 | Validate | Website + Docs`。内部检查名固定为 `Validate Website + Docs`，不随 PR 编号变化，便于设置 required check。
- 合并后的网站发布：`Publish Website | Merge pull request #100 …`。内部任务分别显示 `PR #100 | Pre-publish Check` 和 `PR #100 | Publish Website`。
- 合并后的 Wiki 同步：`Publish Wiki | Merge pull request #100 …`。两个矩阵任务分别显示 `PR #100 | Publish Workbench Wiki` 和 `PR #100 | Publish ArkDB Wiki`。
- 手动运行以 `Manual` 标记来源，并显示阶段和分支；非 `main` 分支的网站运行只检查，Wiki 发布任务仍会跳过。

`scripts\workflow_source.py` 为两条工作流解析来源。PR 事件直接使用事件编号；`push` 事件通过只读 GitHub API 查询提交关联的 PR，只有合并提交 SHA 和目标分支都匹配、且结果唯一时才使用 PR 编号。没有唯一匹配时显示 `Push <短提交 SHA>`，不根据提交说明猜测；API 请求或响应异常会明确失败，不冒充普通 push。来源解析任务只使用 `GITHUB_TOKEN` 的仓库内容和 PR 读取权限，不使用 Wiki 写入令牌。

网站校验 job 使用 `always()`，不会因前置来源解析失败而被跳过；首步检查来源解析结果，任何非 `success` 状态都会明确报错并使校验失败，防止 skipped 的 required check 放行未经校验的 PR。部署仍要求来源解析和网站校验都成功。

顶层 `run-name` 在 job 执行前确定，不能引用来源解析任务的输出，因此 push 运行标题保留原提交说明。标准合并提交说明会包含 PR 编号；直接 push 或自定义说明不保证包含编号，内部发布 job 仍按 API 结果标记。网站一次部署整个 `site`，包含 Workbench 和 ArkDB 两份手册，不拆成两个产品发布任务。

如分支保护此前绑定了旧检查名 `Validate site`，需将其一次性更新为 `Validate Website + Docs`；之后该 PR 检查名保持固定。

## 配置 Wiki 同步

GitHub Wiki 有独立的 `.wiki.git` 仓库，不会直接读取主仓库的 `docs`。`scripts\sync_wiki.py` 负责把文档同步过去，第一次使用前需要完成以下设置。

1. 分别打开[本仓库 Wiki](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/wiki)和 [ArkDB Wiki](https://github.com/OrcaSQL-Workbench/ArkDB/wiki)，确认 Settings 中启用了 Wiki，并创建、保存各自的 `Home` 首页。先写占位内容即可，首次同步时会替换为对应手册首页。仅启用 Wiki 开关不会初始化 `.wiki.git`。
2. 准备一个专用于 Wiki 同步、有到期时间的令牌，令牌所属账号必须能写入**两个目标仓库**的 Wiki。公共 Wiki 通常使用 classic PAT 的 `public_repo` 权限，不要为此授予可访问私有仓库的完整 `repo` 权限，也不要假定默认的 `GITHUB_TOKEN` 能跨仓库写入 Wiki。
3. 由令牌持有者在**本文档仓库**的 **Settings → Secrets and variables → Actions** 中添加或更新 `WIKI_SYNC_TOKEN`。令牌只放在 Secrets 中，不要写进代码、文档、命令参数或聊天。
4. 从 `main` 手动运行 **Sync documentation Wiki**。

设置完成后，文档更改合并到 `main` 就会自动同步。工作流文件是 `.github\workflows\wiki.yml`；`workbench`、`arkdb` 两个矩阵任务分别导出、克隆并普通推送各自的 Wiki，一个失败不会取消另一个。工作流只能从本文档仓库的 `main` 运行，不会将 ArkDB 手册写进 Workbench Wiki。

Wiki 只是文档镜像。直接在 Wiki 修改由脚本管理的页面，下次同步可能会覆盖这些修改。脚本会保留 Wiki 的 Git 历史，不会强制推送，也不会删除它未管理的页面。

## Wiki 同步失败时

先检查 Wiki 是否已保存过首页，再检查 `WIKI_SYNC_TOKEN` 是否已配置、是否过期，以及是否有写入权限。

需要更换令牌时，由令牌持有者更新 Actions Secrets，然后重新运行同步工作流。缺少初始化或授权时，任务会报错，不会跳过同步后显示成功。

Wiki 同步与网站发布是两个独立工作流，Wiki 同步失败不影响网站发布。
