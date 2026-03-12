# 包格式转换说明

当输入对象已经是现成的软件包，而不是源码项目时，参考这份说明。

## 封装的命令

封装脚本会根据输入类型调用对应命令：

- `deb`：`ll-pica deb convert`
- `appimage`：`ll-pica appimage convert`
- `flatpak`：`ll-pica flatpak convert`

如果系统中没有 `ll-pica`，或者当前 `ll-pica` 不支持对应子命令，应停止操作，并提示用户安装或升级 `linglong-pica`。`ll-pica` 由 `linglong-pica` 包提供。

## 使用示例

```bash
bash scripts/convert_package.sh deb ./pkg.deb --workdir /tmp/pica-work --build
bash scripts/convert_package.sh appimage ./pkg.AppImage --id io.github.demo.app --version 1.0.0.0 --build
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

## 失败后的排查顺序

遇到转换失败时，建议按以下顺序排查：

1. 直接重跑脚本打印出的底层命令，并根据需要补充 `--help` 或其他调试参数。
2. 确认系统中安装的 `linglong-pica` 是否包含对应的转换能力。
3. 如果转换对象是 Flatpak，再额外确认 `flatpak` 和 `ostree` 是否可用。
