# third-party-ace-hub-demo

演示如何将一个已有的本地项目接入 ACE（通过 repo 级别的 `.ace` 目录）。

## 项目结构

```
.
├── xarm_vision/                       ← 已有项目代码（纯业务逻辑，不依赖 ACE）
│   ├── __init__.py
│   └── core.py                        ← XArmVisionCore 模拟器核心
│
├── .ace/                              ← ACE 配置与适配层
│   ├── devices/xarm-vision/
│   │   ├── device.json                ← 设备元数据
│   │   └── device.py                  ← ACE 适配器（薄包装，调用 xarm_vision.core）
│   ├── nodes/xarm-vision/
│   │   └── …/node.json                ← 节点元数据
│   └── workflows/
│       └── stack_3_blocks.json        ← 工作流定义
│
├── pyproject.toml                     ← 项目包配置
└── README.md
```

## 核心思想

- **`xarm_vision/`** 是一个独立的 Python 包，包含机械臂模拟器的全部业务逻辑（运动、抓取、拍照、物体检测）。它**完全不依赖 ACE**。
- **`.ace/devices/xarm-vision/device.py`** 是 ACE 的**适配层**：它继承 `SimulatorDevice`，把 ACE 的 `execute_operation` 调用转发给 `xarm_vision.core.XArmVisionCore`，并把返回结果包装成 ACE 的 `OperationResult`。
- 这样一来，这个 repo 展示的是：**“我已经有一个 xarm_vision 项目，现在我要把它接入 ACE”**，而不是把所有东西都塞进 `.ace` 里。
