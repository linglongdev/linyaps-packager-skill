# 源码项目打包说明

当输入对象是源码项目、源码压缩包、下载地址，或 Git / GitHub 仓库地址时，参考这份说明。

## 支持的输入类型

- 本地项目目录
- 本地源码压缩包
- 远程源码压缩包地址
- Git 仓库地址
- GitHub 仓库地址

## 脚本入口

执行方式如下：

```bash
python3 scripts/build_from_project.py --input <source> --workdir <dir>
```

使用前请确认：

- `ll-builder` 已可用。该命令由 `linglong-builder` 包提供。
- `ll-cli` 已可用。该命令由 `linglong-bin` 包提供。

脚本会依次完成以下工作：

1. 将输入整理到 `<workdir>/source-tree`
2. 识别项目使用的构建系统
3. 推断包的元数据、依赖和构建规则
4. 以 `templates/simple.yaml` 为模板、参考 `resources/linglong-schemas.json` 生成以下文件：
   - `<workdir>/linglong.yaml`
   - `<workdir>/inference-report.md`
5. 生成后立即按 `resources/linglong-schemas.json` 做严格校验，至少检查：
   - 是否缺少必填字段
   - 是否出现 schema 未定义字段
   - 字段类型是否正确
   - 是否残留模板占位符
6. 如果没有使用 `--skip-build`，继续执行 `ll-builder build`
7. 如果没有使用 `--skip-export`，继续执行 `ll-builder list` 和 `ll-builder export --ref ...`

如果当前工作区中存在 `demo/` 目录，脚本还会尽量在推断报告中给出与当前项目最接近的示例路径，方便对照参考。

## ll-builder 构建环境约束

执行 `ll-builder build` 时，建议始终记住以下约束：

- 构建容器会以 `base` 作为 rootfs，并把项目目录挂载到容器内的 `/project`。
- 如果配置了 `runtime`，构建时会一并挂载对应的 runtime。
- 构建产物应安装到 `$PREFIX`，不要写入 `/usr`、`/opt` 等宿主式路径。
- 在构建容器中，通常只应假设 `/tmp`、`/project` 和 `$PREFIX` 可写。
- 如果需要使用 `sources` 下载的文件，构建脚本里应从 `/project/linglong/sources/` 读取。

## 推断顺序

脚本的判断顺序如下：

1. 用户在命令行中显式传入的参数
2. 项目自身提供的文档说明
3. 当前工作区中的相似 `demo/` 示例
4. 构建文件和目录结构的特征
5. 保守默认值

## 当前支持的构建系统

- CMake
- Meson
- qmake
- npm
- Python（`pyproject.toml` 或 `setup.py`）
- Go
- Make

如果无法识别构建系统，脚本会生成带 TODO 的 `build` 模板，并以非零状态退出，提示人工补充。

## 建议优先检查的字段

生成结果出来后，优先检查以下内容：

- `package.id`
- `package.version`
- `base`
- `runtime`
- `buildext.apt.build_depends`
- `buildext.apt.depends`
- `build`

同时确认没有多写模板外字段，尤其不要把已经由 `base/runtime` 提供的包重复写入 `buildext`。

## 内置规则摘要

如果项目自身没有给出更明确的打包说明，按以下规则处理：

- `buildext.apt.build_depends` 用于记录构建阶段依赖。
- `buildext.apt.depends` 用于记录运行阶段依赖。
- 自动生成的构建规则必须遵循 `PREFIX` 和 `DESTDIR`。
- 输入为本地目录或本地源码包时，生成的 manifest 可以不包含远程 `sources`。
- 如果项目里已经存在 `linglong.yaml`，应继续沿用当前源码目录布局，不要为了生成新 manifest 再补写远程 `sources`。
- manifest 的字段结构以 `resources/linglong-schemas.json` 为准，输出基础模板为 `templates/simple.yaml`。

## 示例参考策略

如果当前工作区下提供了 `demo/` 示例，建议按以下方式使用：

- 先找构建系统相同的示例，例如 CMake、qmake、QML、Wine。
- 再看框架是否相近，例如 Qt5、DTK5、Qt6、WebEngine。
- 优先参考示例中的 `base`、`runtime`、`command` 和 `build` 段。
- 不要直接照抄包名、版本号、启动命令和安装路径，必须结合目标项目实际情况修改。

## base 和 runtime 的选型规则

- 优先选择稳定版本组合。
- Qt6 或 DTK6 项目：`org.deepin.base/25.2.1` + `org.deepin.runtime.dtk/25.2.1`
- Qt6 WebEngine 项目：`org.deepin.base/25.2.0` + `org.deepin.runtime.webengine/25.2.0`
- Qt5 或 DTK5 项目：`org.deepin.base/23.1.0` + `org.deepin.runtime.dtk/23.1.0`
- 如果项目的框架依赖不明确：`runtime` 可以留空，`base` 采用较为稳妥的选择
- 在确定版本系列后，脚本会优先查询远程仓库，选择最新可用的版本系列，并把 `base` 和 `runtime` 写成符合玲珑配置要求的三段式版本。
- `references/runtime.md` 中列出的 base/runtime 已内置包，不需要重复写入 `buildext.apt.build_depends` 或 `buildext.apt.depends`。

## 远程版本校验

如果需要确认远程仓库中实际可用的版本，可以直接使用：

- `ll-cli search org.deepin.base --show-all-version`
- `ll-cli search org.deepin.runtime.dtk --show-all-version`

在版本冲突或依赖拉取失败时，应优先以远程仓库中真实存在的版本为准。

如果系统中没有 `ll-cli`，脚本会停止，并提示先安装 `linglong-bin`。

## ll-builder 的使用顺序

- 构建：`ll-builder build`
- 查看可导出 ref：`ll-builder list`
- 导出：`ll-builder export --ref <selected-ref>`

如果系统中没有 `ll-builder`，脚本会停止，并提示先安装 `linglong-builder`。
