#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
import zipfile
import re


class CommitToMod:
    def __init__(self, commit_id=None, mod_name="newmode", mod_version="1"):
        self.commit_id = commit_id
        self.mod_name = mod_name
        self.mod_version = mod_version
        self.output_dir = Path("output")
        self.mod_dir = self.output_dir / self.mod_name
        self.game_dir = self.mod_dir / "game"
        self.boot_json_path = self.mod_dir / "boot.json"
        self.twee_replacer_params = []
        self.replace_patcher_params = {"js": []}
        self.twee_file_list = []
        self.modified_files = []
        self.new_files = []

    def prepare_directories(self):
        """创建必要的目录结构"""
        if not self.output_dir.exists():
            self.output_dir.mkdir()
        
        if self.mod_dir.exists():
            shutil.rmtree(self.mod_dir)
        
        self.mod_dir.mkdir()
        self.game_dir.mkdir()

    def get_latest_commit_id(self):
        """获取最近的一次提交ID"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"获取最近提交ID失败: {e}")
            sys.exit(1)

    def get_commit_changes(self):
        """获取指定commit的变更"""
        if not self.commit_id:
            self.commit_id = self.get_latest_commit_id()
            print(f"使用最近的提交: {self.commit_id}")
        
        try:
            # 获取变更的文件列表
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", self.commit_id],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                    
                parts = line.split()
                change_type = parts[0]
                file_path = parts[1]
                
                if change_type == "D":
                    # 忽略删除的文件
                    continue
                elif change_type == "A":
                    # 新增的文件
                    self.new_files.append(file_path)
                elif change_type in ["M", "R"]:
                    # 修改的文件
                    self.modified_files.append(file_path)
            
            print(f"新增文件: {len(self.new_files)}")
            print(f"修改文件: {len(self.modified_files)}")
            
        except subprocess.CalledProcessError as e:
            print(f"获取提交变更失败: {e}")
            sys.exit(1)

    def copy_new_files(self):
        """复制新增的文件到MOD目录"""
        for file_path in self.new_files:
            # 创建目标路径
            dest_path = self.mod_dir / file_path
            dest_dir = dest_path.parent
            
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True)
            
            try:
                # 从git仓库中获取文件内容
                result = subprocess.run(
                    ["git", "show", f"{self.commit_id}:{file_path}"],
                    capture_output=True,
                    check=True
                )
                
                # 写入文件
                with open(dest_path, "wb") as f:
                    f.write(result.stdout)
                
                # 如果是twee文件，添加到twee文件列表
                if file_path.endswith(".twee"):
                    self.twee_file_list.append(file_path)
                    
            except subprocess.CalledProcessError as e:
                print(f"复制文件 {file_path} 失败: {e}")

    def process_modified_files(self):
        """处理修改的文件，提取差异"""
        for file_path in self.modified_files:
            if file_path.endswith(".twee"):
                self.process_modified_twee(file_path)
            elif file_path.endswith(".js"):
                self.process_modified_js(file_path)

    def get_passage_name(self, file_path, line_number):
        """获取Twee文件中指定行所属的段落名称"""
        try:
            # 从git仓库获取文件内容
            result = subprocess.run(
                ["git", "show", f"{self.commit_id}:{file_path}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            lines = result.stdout.splitlines()
            
            # 从指定行向上搜索第一个::开头的行
            for i in range(line_number, -1, -1):
                if i >= len(lines):
                    continue
                    
                line = lines[i]
                if line.startswith("::"):
                    # 提取段落名称，去除[widget]标记
                    passage_name = line[2:].strip()
                    passage_name = re.sub(r'\[widget\]', '', passage_name).strip()
                    return passage_name
            
            return "Unknown Passage"
            
        except subprocess.CalledProcessError as e:
            print(f"获取段落名称失败: {e}")
            return "Unknown Passage"

    def process_modified_twee(self, file_path):
        """处理修改的Twee文件，提取差异并添加到TweeReplacer参数"""
        try:
            # 获取文件差异
            result = subprocess.run(
                ["git", "diff", f"{self.commit_id}~1", self.commit_id, "--", file_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            diff_content = result.stdout
            
            # 解析差异块
            diff_blocks = re.findall(r'@@ -(\d+),\d+ \+(\d+),\d+ @@([\s\S]+?)(?=@@ |\Z)', diff_content)
            
            for old_line, new_line, block_content in diff_blocks:
                old_line = int(old_line)
                new_line = int(new_line)
                
                # 分离添加和删除的行
                added_lines = []
                removed_lines = []
                context_before = []
                context_after = []
                
                lines = block_content.splitlines()
                in_context_before = True
                has_changes = False
                
                # 收集所有上下文行，用于后续处理
                all_context_lines = []
                for line in lines:
                    if not line:
                        continue
                    if line.startswith(" "):
                        all_context_lines.append(line[1:])
                
                for line in lines:
                    if not line:
                        continue
                        
                    if line.startswith("+") and not line.startswith("++"):
                        added_lines.append(line[1:])
                        in_context_before = False
                        has_changes = True
                    elif line.startswith("-") and not line.startswith("--"):
                        removed_lines.append(line[1:])
                        in_context_before = False
                        has_changes = True
                    else:
                        # 上下文行
                        if line.startswith(" "):
                            line = line[1:]
                        if in_context_before:
                            context_before.append(line)
                        elif not in_context_before:
                            context_after.append(line)
                
                if has_changes:
                    # 获取段落名称
                    passage_name = self.get_passage_name(file_path, old_line)
                    
                    # 根据不同情况构建findString和replace
                    if added_lines and not removed_lines:
                        # 只有添加的行
                        find_string = "\n".join(context_before)
                        replace = "\n".join(context_before + added_lines)
                    elif removed_lines and not added_lines:
                        # 只有删除的行
                        find_string = "\n".join(context_before + removed_lines)
                        replace = "\n".join(context_before)
                    else:
                        # 同时有添加和删除的行
                        find_string = "\n".join(context_before + removed_lines)
                        replace = "\n".join(context_before + added_lines)
                    
                    # 添加到TweeReplacer参数
                    self.twee_replacer_params.append({
                        "passage": passage_name,
                        "findString": find_string,
                        "replace": replace
                    })
            
        except subprocess.CalledProcessError as e:
            print(f"处理Twee文件 {file_path} 差异失败: {e}")

    def process_modified_js(self, file_path):
        """处理修改的JS文件，提取差异并添加到ReplacePatcher参数"""
        try:
            # 获取文件差异
            result = subprocess.run(
                ["git", "diff", f"{self.commit_id}~1", self.commit_id, "--", file_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            diff_content = result.stdout
            
            # 解析差异块
            diff_blocks = re.findall(r'@@ -(\d+),\d+ \+(\d+),\d+ @@([\s\S]+?)(?=@@ |\Z)', diff_content)
            
            for old_line, new_line, block_content in diff_blocks:
                # 分离添加和删除的行
                added_lines = []
                removed_lines = []
                context_before = []
                
                lines = block_content.splitlines()
                in_context_before = True
                has_changes = False
                
                for line in lines:
                    if not line:
                        continue
                        
                    if line.startswith("+") and not line.startswith("++"):
                        added_lines.append(line[1:])
                        in_context_before = False
                        has_changes = True
                    elif line.startswith("-") and not line.startswith("--"):
                        removed_lines.append(line[1:])
                        in_context_before = False
                        has_changes = True
                    else:
                        # 上下文行
                        if line.startswith(" "):
                            line = line[1:]
                        if in_context_before and len(context_before) < 2:
                            context_before.append(line)
                
                if has_changes:
                    # 根据不同情况构建from和to
                    if added_lines and not removed_lines:
                        # 只有添加的行
                        from_string = "\n".join(context_before)
                        to_string = "\n".join(context_before + added_lines)
                    elif removed_lines and not added_lines:
                        # 只有删除的行
                        from_string = "\n".join(context_before + removed_lines)
                        to_string = "\n".join(context_before)
                    else:
                        # 同时有添加和删除的行
                        from_string = "\n".join(context_before + removed_lines)
                        to_string = "\n".join(context_before + added_lines)
                    
                    # 添加到ReplacePatcher参数
                    self.replace_patcher_params["js"].append({
                        "from": from_string,
                        "to": to_string,
                        "fileName": os.path.basename(file_path)
                    })
            
        except subprocess.CalledProcessError as e:
            print(f"处理JS文件 {file_path} 差异失败: {e}")

    def generate_boot_json(self):
        """生成boot.json文件"""
        # 构建tweeFileList，使用set去重
        twee_files = set()
        for file_path in self.new_files:
            if file_path.endswith(".twee"):
                twee_files.add(file_path)
        
        # 将set转换回list
        self.twee_file_list = list(twee_files)
        
        # 构建boot.json内容
        boot_json = {
            "name": self.mod_name,
            "version": self.mod_version,
            "styleFileList": [],
            "scriptFileList_inject_early": [],
            "scriptFileList": [],
            "tweeFileList": self.twee_file_list,
            "imgFileList": [],
            "additionFile": [],
            "addonPlugin": [
                {
                    "modName": "TweeReplacer",
                    "addonName": "TweeReplacerAddon",
                    "modVersion": "1.0.0",
                    "params": self.twee_replacer_params
                }
            ],
            "dependenceInfo": [
                {
                    "modName": "TweeReplacer",
                    "version": "^1.0.0"
                },
            ]
        }
        
        # 如果有JS文件差异，添加ReplacePatcher插件
        if self.replace_patcher_params["js"]:
            boot_json["addonPlugin"].append({
                "modName": "ReplacePatcher",
                "addonName": "ReplacePatcherAddon",
                "modVersion": "^1.0.0",
                "params": self.replace_patcher_params
            })
            boot_json["dependenceInfo"].append({
                    "modName": "ReplacePatcher",
                    "version": ">=1.0.0"
                })
        
        # 写入boot.json文件
        with open(self.boot_json_path, "w", encoding="utf-8") as f:
            json.dump(boot_json, f, ensure_ascii=False, indent=4)
            
        print(f"生成boot.json文件: {self.boot_json_path}")

    def create_zip(self):
        """将MOD目录打包为zip文件"""
        zip_name = f"DoL-{self.mod_name}-{self.mod_version}.zip"
        zip_path = self.output_dir / zip_name
        
        # 如果zip文件已存在，先删除
        if zip_path.exists():
            zip_path.unlink()
        
        # 创建zip文件
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.mod_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(self.mod_dir)
                    zipf.write(file_path, rel_path)
        
        print(f"创建zip文件: {zip_path}")
        return zip_path

    def run(self):
        """执行MOD生成流程"""
        self.prepare_directories()
        self.get_commit_changes()
        self.copy_new_files()
        self.process_modified_files()
        self.generate_boot_json()
        zip_path = self.create_zip()
        print(f"MOD生成完成: {zip_path}")
        print(f"MOD目录: {self.mod_dir}")


def main():
    parser = argparse.ArgumentParser(description="根据Git提交生成DoL MOD")
    parser.add_argument("--commit", "-c", help="指定CommitID，默认使用最近的提交")
    parser.add_argument("--name", "-n", default="newmode", help="MOD名称，默认为newmode")
    parser.add_argument("--version", "-v", default="1", help="MOD版本，默认为1")
    
    args = parser.parse_args()
    
    converter = CommitToMod(args.commit, args.name, args.version)
    converter.run()


if __name__ == "__main__":
    main()
