"""
测试数据管理模块

提供统一的测试数据加载和管理接口：
- 支持 YAML 和 JSON 格式
- 支持按模块组织数据
- 支持数据继承和覆盖
- 支持环境变量替换
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from config.settings import settings
from core.logger import get_logger

logger = get_logger("data_loader")


class DataLoadError(Exception):
    """数据加载异常"""
    pass


class DataLoader:
    """测试数据加载器"""

    _cache: Dict[str, Any] = {}

    def __init__(self, data_dir: Optional[Path] = None):
        """
        初始化数据加载器

        Args:
            data_dir: 数据文件目录，默认为 tests/data
        """
        self.data_dir = data_dir or settings.PROJECT_ROOT / "tests" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load(self, file_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        加载测试数据文件

        Args:
            file_path: 相对于 data_dir 的文件路径
            use_cache: 是否使用缓存

        Returns:
            解析后的数据字典
        """
        cache_key = str(file_path)

        if use_cache and cache_key in self._cache:
            logger.debug(f"[数据加载] 从缓存读取: {file_path}")
            return self._cache[cache_key]

        full_path = self.data_dir / file_path

        if not full_path.exists():
            raise DataLoadError(f"数据文件不存在: {full_path}")

        suffix = full_path.suffix.lower()

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                if suffix in (".yaml", ".yml"):
                    data = yaml.safe_load(f) or {}
                elif suffix == ".json":
                    data = json.load(f)
                else:
                    raise DataLoadError(f"不支持的文件格式: {suffix}")

            # 处理环境变量替换
            data = self._resolve_env_vars(data)

            if use_cache:
                self._cache[cache_key] = data

            logger.info(f"[数据加载] {file_path} → {len(data)} 项")
            return data

        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise DataLoadError(f"数据文件解析失败: {file_path}, 错误: {e}")

    def load_module_data(self, module: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        加载模块测试数据

        优先级: {module}/{ENV}.yaml > {module}/common.yaml

        Args:
            module: 模块名称（如 login, console, ops）
            use_cache: 是否使用缓存

        Returns:
            合并后的模块数据
        """
        env = settings.ENV
        env_file = f"{module}/{env}.yaml"
        common_file = f"{module}/common.yaml"

        # 先加载通用数据
        common_data = {}
        common_path = self.data_dir / common_file
        if common_path.exists():
            common_data = self.load(common_file, use_cache)

        # 再加载环境特定数据（覆盖通用数据）
        env_data = {}
        env_path = self.data_dir / env_file
        if env_path.exists():
            env_data = self.load(env_file, use_cache)

        # 合并数据
        merged = self._deep_merge(common_data, env_data)
        logger.debug(f"[模块数据] {module} → {len(merged)} 项")
        return merged

    def get_case_data(
        self,
        module: str,
        case_name: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        获取特定测试用例的数据

        Args:
            module: 模块名称
            case_name: 用例名称
            use_cache: 是否使用缓存

        Returns:
            用例数据
        """
        module_data = self.load_module_data(module, use_cache)
        case_data = module_data.get(case_name, {})

        if not case_data:
            logger.warning(f"[用例数据] 未找到 {module}.{case_name}")

        return case_data

    def get_parametrize_data(
        self,
        module: str,
        case_name: str,
        param_name: str = "cases",
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取参数化测试数据

        Args:
            module: 模块名称
            case_name: 用例名称
            param_name: 参数列表字段名，默认为 "cases"
            use_cache: 是否使用缓存

        Returns:
            参数化数据列表
        """
        case_data = self.get_case_data(module, case_name, use_cache)
        params = case_data.get(param_name, [])

        if not params:
            logger.warning(f"[参数化数据] 未找到 {module}.{case_name}.{param_name}")

        return params

    def _resolve_env_vars(self, data: Any) -> Any:
        """
        递归解析数据中的环境变量

        支持 ${VAR_NAME} 和 ${VAR_NAME:default} 格式
        """
        import os
        import re

        if isinstance(data, str):
            # 匹配 ${VAR} 或 ${VAR:default}
            pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

            def replace_var(match):
                var_name = match.group(1)
                default = match.group(2)
                value = os.getenv(var_name, default)
                return value if value is not None else match.group(0)

            return re.sub(pattern, replace_var, data)

        elif isinstance(data, dict):
            return {k: self._resolve_env_vars(v) for k, v in data.items()}

        elif isinstance(data, list):
            return [self._resolve_env_vars(item) for item in data]

        return data

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        深度合并两个字典
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def clear_cache(self):
        """清空数据缓存"""
        self._cache.clear()
        logger.info("[数据缓存] 已清空")


# 全局数据加载器实例
data_loader = DataLoader()


# 便捷函数
def load_data(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """加载测试数据文件"""
    return data_loader.load(file_path, use_cache)


def load_module_data(module: str, use_cache: bool = True) -> Dict[str, Any]:
    """加载模块测试数据"""
    return data_loader.load_module_data(module, use_cache)


def get_case_data(module: str, case_name: str, use_cache: bool = True) -> Dict[str, Any]:
    """获取测试用例数据"""
    return data_loader.get_case_data(module, case_name, use_cache)


def get_parametrize_data(
    module: str,
    case_name: str,
    param_name: str = "cases",
    use_cache: bool = True
) -> List[Dict[str, Any]]:
    """获取参数化测试数据"""
    return data_loader.get_parametrize_data(module, case_name, param_name, use_cache)
