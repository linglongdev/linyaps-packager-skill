# 贡献指南

本文档面向维护“玲珑打包技能”（英文名 `linyaps-packager-skill`）的开发者，说明后续扩展脚本、模板和参考文档时应遵循的基本规则。

## 维护目标

这份 skill 的目标不是生成“看起来像能用”的 `linglong.yaml`，而是尽量稳定地生成结构正确、依赖合理、便于人工复核的结果。

修改时应优先保证以下几点：

- 输出结构稳定
- 规则来源明确
- 文档与脚本保持一致
- 安全边界清晰

## 目录职责

- `SKILL.md`
  定义 skill 的使用场景、执行原则和安全约束。
- `scripts/build_from_project.py`
  负责源码项目分析、manifest 生成、严格校验，以及可选的构建和导出。
- `scripts/convert_package.sh`
  负责 `deb`、`AppImage`、`Flatpak` 转换入口。
- `references/`
  保存规则来源、流程说明、base/runtime 参考信息。
- `templates/simple.yaml`
  定义 manifest 基础结构和字段顺序。
- `resources/linglong-schemas.json`
  定义 manifest 允许出现的字段与类型。

## 修改原则

### 1. 模板优先

生成 `linglong.yaml` 时，应始终优先使用 `templates/simple.yaml`。不要在脚本中随意新增模板之外的字段，也不要绕过模板直接手写另一套输出结构。

### 2. schema 约束必须同步

如果调整了输出字段：

- 先确认 `resources/linglong-schemas.json` 是否允许该字段
- 再确认 `templates/simple.yaml` 是否需要同步调整
- 最后确认脚本中的严格校验逻辑不会被绕过

### 3. 参考文档要能落到代码

如果在 `references/` 里新增或修改规则，应同时确认脚本是否真正实现了该规则。不要只改文档，不改逻辑。

### 4. 规则来源要可追溯

新增启发式规则时，应优先选择以下信息源：

- 项目文档
- `debian/control`
- `debian/changelog`
- `debian/rules`
- 构建配置文件
- `references/runtime.md`
- 当前工作区中的相似 `demo/` 示例

如果规则只来自个人经验，且无法稳定复现，应谨慎加入。

## 安全规范

这是这份 skill 的硬约束。

- 不要在未经确认的情况下删除用户目录中的文件或数据。
- 如果某个操作会删除工作目录之外的内容，必须立即阻塞流程，并明确提示用户确认。
- 临时目录清理只能发生在当前受管工作目录内。
- 不要为了“清理环境”而增加 `rm -rf`、`shutil.rmtree`、`unlink` 等破坏性逻辑，除非已经明确证明目标路径只位于受管临时目录中。

如果需要引入新的删除逻辑，至少应满足：

1. 能证明删除目标位于受管工作目录内。
2. 不会触及用户原始输入目录。
3. 对目标路径做显式校验，而不是依赖调用方保证安全。

## 依赖命令约束

这份 skill 依赖的关键命令和来源如下：

- `ll-builder` 来自 `linglong-builder`
- `ll-cli` 来自 `linglong-bin`
- `ll-pica` 来自 `linglong-pica`

修改脚本时，不要把这些依赖写成“缺失时静默跳过”。如果关键能力缺失，应明确提示用户先安装对应软件包。

## 测试建议

每次修改后，至少应做以下验证：

1. 语法检查

```bash
python3 -B -c 'import ast, pathlib; ast.parse(pathlib.Path("scripts/build_from_project.py").read_text())'
```

自动化回归测试：

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

2. 正向生成验证

```bash
python3 scripts/build_from_project.py --input /path/to/project --workdir /tmp/skill-check --skip-build
```

需要确认：

- `linglong.yaml` 能成功生成
- `inference-report.md` 能成功生成
- manifest 能通过严格校验

3. 负向校验验证

至少构造一份非法 manifest，确认脚本会在以下场景报错：

- schema 外字段
- 缺少必填字段
- 类型错误
- 模板占位符残留

4. 文档一致性检查

确认以下文件描述没有互相冲突：

- `SKILL.md`
- `README.md`
- `README_zh_CN.md`
- `references/project-build-workflow.md`
- `references/pica-convert-workflow.md`
- `references/runtime.md`

## 提交建议

如果一次改动同时修改了脚本、模板和文档，提交说明里应明确指出：

- 改动影响了哪条工作流
- 是否修改了 manifest 结构
- 是否修改了严格校验逻辑
- 是否引入了新的安全约束或删除保护
