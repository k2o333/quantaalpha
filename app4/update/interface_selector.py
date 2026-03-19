"""
接口选择器
根据配置和用户选项选择需要更新的接口
"""
import logging
from typing import List, Optional
import os

from .models import UpdateOptions

logger = logging.getLogger(__name__)


class InterfaceSelector:
    """接口选择器 - 选择需要更新的接口"""
    
    def __init__(self, config_loader):
        self.config_loader = config_loader
        self.update_config = config_loader.global_config.get('update', {})
        self.groups_config = config_loader.global_config.get('groups', {})
    
    def select_interfaces(
        self, 
        options: UpdateOptions
    ) -> List[str]:
        """
        选择需要更新的接口
        
        流程：
        1. 获取所有可用接口
        2. 应用包含/排除规则
        3. 按权限过滤
        4. 按配置顺序排序
        
        Args:
            options: 更新选项
            
        Returns:
            List[str]: 接口名称列表
        """
        # 获取所有可用接口
        all_interfaces = self.config_loader.get_available_interfaces()
        logger.info(f"总共有 {len(all_interfaces)} 个可用接口")
        
        # 应用包含规则
        selected = self._apply_inclusion_rules(all_interfaces, options)
        logger.info(f"应用包含规则后剩余 {len(selected)} 个接口")
        
        # 应用排除规则
        selected = self._apply_exclusions(selected, options)
        logger.info(f"应用排除规则后剩余 {len(selected)} 个接口")
        
        # 按更新顺序排序
        selected = self._sort_by_update_order(selected)
        
        logger.info(f"最终选定 {len(selected)} 个接口进行更新")
        return selected
    
    def _apply_inclusion_rules(
        self, 
        interfaces: List[str], 
        options: UpdateOptions
    ) -> List[str]:
        """
        应用包含规则
        
        优先级：
        1. 如果指定了具体接口，只使用这些接口
        2. 如果指定了组，使用这些组的接口
        3. 否则使用所有接口
        
        Args:
            interfaces: 所有可用接口
            options: 更新选项
            
        Returns:
            List[str]: 过滤后的接口列表
        """
        # 如果指定了具体接口
        if options.interfaces is not None:
            # 验证接口是否存在
            valid_interfaces = []
            for iface in options.interfaces:
                if iface in interfaces:
                    valid_interfaces.append(iface)
                else:
                    logger.warning(f"指定的接口 '{iface}' 不存在，已忽略")
            return valid_interfaces
        
        # 如果指定了组
        if options.groups is not None and len(options.groups) > 0:
            selected = set()
            for group_name in options.groups:
                group_interfaces = self._get_group_interfaces(group_name)
                if group_interfaces:
                    selected.update(group_interfaces)
                    logger.info(f"从组 '{group_name}' 中选择了 {len(group_interfaces)} 个接口")
                else:
                    logger.warning(f"组 '{group_name}' 不存在或为空")
            return list(selected)
        
        # 否则返回所有接口
        return interfaces.copy()
    
    def _get_group_interfaces(self, group_name: str) -> List[str]:
        """
        获取组中的接口列表
        
        Args:
            group_name: 组名称
            
        Returns:
            List[str]: 接口名称列表
        """
        # 从配置中获取组
        if group_name in self.groups_config:
            return self.groups_config[group_name].copy()
        
        # 如果组名对应一个接口，返回该接口
        all_interfaces = self.config_loader.get_available_interfaces()
        if group_name in all_interfaces:
            return [group_name]
        
        return []
    
    def _apply_exclusions(
        self, 
        interfaces: List[str], 
        options: UpdateOptions
    ) -> List[str]:
        """
        应用排除规则
        
        Args:
            interfaces: 接口列表
            options: 更新选项
            
        Returns:
            List[str]: 过滤后的接口列表
        """
        # 获取配置中排除的接口
        config_exclusions = self.update_config.get('excluded_interfaces', [])
        
        # 合并所有排除项
        all_exclusions = set(config_exclusions)
        if options.exclude:
            all_exclusions.update(options.exclude)
        
        # 如果没有排除项，直接返回
        if not all_exclusions:
            return interfaces
        
        filtered = []
        for iface in interfaces:
            if iface in all_exclusions:
                logger.debug(f"接口 '{iface}' 被排除")
            else:
                filtered.append(iface)
        
        return filtered
    
    def _sort_by_update_order(
        self, 
        interfaces: List[str]
    ) -> List[str]:
        """
        按配置的更新顺序排序
        
        未在配置中指定的接口按字母顺序排在最后
        
        Args:
            interfaces: 接口列表
            
        Returns:
            List[str]: 排序后的接口列表
        """
        update_order = self.update_config.get('update_order', [])
        
        # 创建顺序映射
        order_map = {name: idx for idx, name in enumerate(update_order)}
        
        # 排序：在配置中的按顺序，不在配置中的按字母顺序排在最后
        def sort_key(iface):
            if iface in order_map:
                return (0, order_map[iface])
            else:
                return (1, iface)
        
        return sorted(interfaces, key=sort_key)
    
    def filter_by_permission(
        self, 
        interfaces: List[str], 
        available_points: int
    ) -> List[str]:
        """
        根据积分权限过滤接口
        
        Args:
            interfaces: 接口列表
            available_points: 可用积分
            
        Returns:
            List[str]: 过滤后的接口列表
        """
        filtered = []
        
        for iface in interfaces:
            try:
                config = self.config_loader.get_interface_config(iface)
                permissions = config.get('permissions', {})
                min_points = permissions.get('min_points', 0)
                
                if available_points >= min_points:
                    filtered.append(iface)
                else:
                    logger.warning(
                        f"接口 '{iface}' 需要 {min_points} 积分，"
                        f"当前只有 {available_points} 积分，已跳过"
                    )
            except Exception as e:
                logger.warning(f"检查接口 '{iface}' 权限时出错: {e}")
                # 默认包含
                filtered.append(iface)
        
        return filtered
    
    def get_interface_info(self, interface_name: str) -> Optional[dict]:
        """
        获取接口信息
        
        Args:
            interface_name: 接口名称
            
        Returns:
            Optional[dict]: 接口信息字典
        """
        try:
            config = self.config_loader.get_interface_config(interface_name)
            return {
                'name': interface_name,
                'description': config.get('description', ''),
                'api_name': config.get('api_name', interface_name),
                'min_points': config.get('permissions', {}).get('min_points', 0),
            }
        except Exception as e:
            logger.warning(f"获取接口 '{interface_name}' 信息时出错: {e}")
            return None
