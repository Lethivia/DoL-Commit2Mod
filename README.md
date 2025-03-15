# DoL-Commit2Mod

一个适用于Degrees of Lewdity的根据Git提交生成MOD的工具。

## 功能

该工具可以根据指定的Git提交ID，自动生成一个符合DoL MOD格式的目录结构，并将其打包为zip文件。具体功能包括：

1. 分析指定Commit的变更内容
2. 将新增的文件按原目录结构放到MOD目录中
3. 提取修改的Twee文件差异，填写到TweeReplacer参数中
4. 提取修改的JS文件差异，填写到ReplacePatcher参数中
5. 生成符合要求的boot.json文件
6. 将MOD目录打包为zip文件

## 使用方法

```bash
python main.py [--commit COMMIT_ID] [--name MOD_NAME] [--version MOD_VERSION]
```

### 参数说明

- `--commit`, `-c`: 指定Git提交ID，如果不指定则使用最近的一次提交
- `--name`, `-n`: MOD名称，默认为"newmode"
- `--version`, `-v`: MOD版本，默认为"1"

### 示例

```bash
# 使用最近的提交，生成默认名称和版本的MOD
python main.py

# 指定提交ID，自定义MOD名称和版本
python main.py --commit abc123def456 --name mymod --version 1.0
```

## 输出

程序会在当前目录下创建一个`output`目录，其中包含：

1. 生成的MOD目录（目录名为MOD名称）
2. 打包好的zip文件（文件名格式为`DoL-{MOD名称}-{MOD版本}.zip`）

## 注意事项

- 该工具需要在Git仓库目录下运行
- 对于删除整个文件类型的变更，工具会忽略不处理
