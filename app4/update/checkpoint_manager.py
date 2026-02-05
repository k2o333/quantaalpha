"""
断点续传管理器
管理更新进度，支持断点续传
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CheckpointManager:
    """断点管理器 - 保存和恢复更新进度"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化断点管理器
        
        Args:
            config: 断点配置字典
        """
        self.enabled = config.get('enabled', True)
        self.filepath = config.get('file', 'data/.update_checkpoint.json')
        self.interval = config.get('interval', 10)
        self.auto_resume = config.get('auto_resume', True)
        
        self._checkpoint_data = {
            'version': '1.0',
            'created_at': None,
            'updated_at': None,
            'completed_interfaces': [],
            'failed_interfaces': {},
            'current_interface': None,
            'options': {}
        }
    
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        加载断点文件
        
        Returns:
            Optional[Dict[str, Any]]: 断点数据，如果不存在或禁用则返回None
        """
        if not self.enabled or not os.path.exists(self.filepath):
            return None
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"加载断点文件: {self.filepath}")
            self._checkpoint_data = data
            return data
        except Exception as e:
            logger.warning(f"加载断点文件失败: {e}")
            return None
    
    def save_checkpoint(self):
        """保存断点文件"""
        if not self.enabled:
            return
        
        self._checkpoint_data['updated_at'] = datetime.now().isoformat()
        
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._checkpoint_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"保存断点文件: {self.filepath}")
        except Exception as e:
            logger.warning(f"保存断点文件失败: {e}")
    
    def initialize_checkpoint(self, options: Dict[str, Any]):
        """
        初始化新的断点
        
        Args:
            options: 更新选项
        """
        self._checkpoint_data = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'completed_interfaces': [],
            'failed_interfaces': {},
            'current_interface': None,
            'options': options
        }
        
        if self.enabled:
            self.save_checkpoint()
            logger.info("初始化新的断点记录")
    
    def record_interface_start(self, interface_name: str):
        """
        记录接口开始
        
        Args:
            interface_name: 接口名称
        """
        self._checkpoint_data['current_interface'] = interface_name
        logger.debug(f"记录接口开始: {interface_name}")
    
    def record_interface_complete(self, interface_name: str, success: bool, error_message: str = None):
        """
        记录接口完成
        
        Args:
            interface_name: 接口名称
            success: 是否成功
            error_message: 错误信息（如果失败）
        """
        if success:
            self._checkpoint_data['completed_interfaces'].append(interface_name)
            # 如果之前在失败列表中，移除它
            if interface_name in self._checkpoint_data['failed_interfaces']:
                del self._checkpoint_data['failed_interfaces'][interface_name]
        else:
            self._checkpoint_data['failed_interfaces'][interface_name] = {
                'timestamp': datetime.now().isoformat(),
                'error': error_message
            }
        
        self._checkpoint_data['current_interface'] = None
        
        # 按间隔保存
        if self.enabled:
            total_completed = len(self._checkpoint_data['completed_interfaces'])
            if total_completed % self.interval == 0:
                self.save_checkpoint()
    
    def is_interface_completed(self, interface_name: str) -> bool:
        """
        检查接口是否已完成
        
        Args:
            interface_name: 接口名称
            
        Returns:
            bool: 是否已完成
        """
        return interface_name in self._checkpoint_data['completed_interfaces']
    
    def is_interface_failed(self, interface_name: str) -> bool:
        """
        检查接口是否失败过
        
        Args:
            interface_name: 接口名称
            
        Returns:
            bool: 是否失败过
        """
        return interface_name in self._checkpoint_data['failed_interfaces']
    
    def get_failed_interfaces(self) -> Dict[str, Dict[str, str]]:
        """
        获取失败的接口列表
        
        Returns:
            Dict[str, Dict[str, str]]: 失败的接口信息
        """
        return self._checkpoint_data['failed_interfaces'].copy()
    
    def clear_checkpoint(self):
        """清除断点文件"""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
            logger.info(f"清除断点文件: {self.filepath}")
        
        # 重置数据
        self._checkpoint_data = {
            'version': '1.0',
            'created_at': None,
            'updated_at': None,
            'completed_interfaces': [],
            'failed_interfaces': {},
            'current_interface': None,
            'options': {}
        }
    
    def get_resume_interfaces(self, all_interfaces: List[str]) -> List[str]:
        """
        获取需要恢复更新的接口列表
        
        Args:
            all_interfaces: 所有接口列表
            
        Returns:
            List[str]: 需要更新的接口列表
        """
        completed = set(self._checkpoint_data['completed_interfaces'])
        return [i for i in all_interfaces if i not in completed]
    
    def get_checkpoint_summary(self) -> Dict[str, Any]:
        """
        获取断点摘要信息
        
        Returns:
            Dict[str, Any]: 断点摘要
        """
        total_completed = len(self._checkpoint_data['completed_interfaces'])
        total_failed = len(self._checkpoint_data['failed_interfaces'])
        current = self._checkpoint_data['current_interface']
        
        return {
            'total_completed': total_completed,
            'total_failed': total_failed,
            'current_interface': current,
            'created_at': self._checkpoint_data['created_at'],
            'updated_at': self._checkpoint_data['updated_at']
        }
    
    def should_resume(self) -> bool:
        """
        判断是否应该恢复更新
        
        Returns:
            bool: 是否应该恢复
        """
        if not self.enabled or not self.auto_resume:
            return False
        
        if not os.path.exists(self.filepath):
            return False
        
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return False
        
        # 检查是否有未完成的接口
        completed = set(checkpoint.get('completed_interfaces', []))
        
        # 如果有当前正在处理的接口或已完成部分接口，则应该恢复
        if checkpoint.get('current_interface') or len(completed) > 0:
            return True
        
        return False
    
    def validate_options_compatibility(self, current_options: Dict[str, Any]) -> bool:
        """
        验证当前选项与断点选项的兼容性
        
        Args:
            current_options: 当前更新选项
            
        Returns:
            bool: 是否兼容
        """
        checkpoint_options = self._checkpoint_data.get('options', {})
        
        # 如果断点没有保存选项，认为兼容
        if not checkpoint_options:
            return True
        
        # 检查关键选项是否一致
        # 主要检查接口列表和日期范围
        key_fields = ['interfaces', 'groups', 'start_date', 'end_date', 'force']
        
        for field in key_fields:
            if field in checkpoint_options and field in current_options:
                if checkpoint_options[field] != current_options[field]:
                    logger.warning(
                        f"断点选项不兼容: {field} "
                        f"(断点: {checkpoint_options[field]}, 当前: {current_options[field]})"
                    )
                    return False
        
        return True
