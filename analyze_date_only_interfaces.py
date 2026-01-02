#!/usr/bin/env python3
"""
分析接口配置文件，找出只使用日期参数的接口
"""

import os
import re
from pathlib import Path

def analyze_interface_params(file_path):
    """分析单个接口配置文件的参数"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找parameters部分
    param_match = re.search(r'^parameters:\s*\n((?:\s+.+\n)*)', content, re.MULTILINE)
    if not param_match:
        return [], False  # 没有找到parameters部分
    
    params_section = param_match.group(1)
    
    # 提取参数名
    param_names = []
    for line in params_section.split('\n'):
        # 匹配参数名，如 '  ts_code:' 或 '  start_date:'
        match = re.match(r'^\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:', line)
        if match:
            param_names.append(match.group(1))
    
    # 定义日期参数列表
    date_params = {
        'start_date', 'end_date', 'trade_date', 'ann_date', 'period', 'month', 
        'date', 'pub_date', 'due_date', 'list_date', 'delist_date', 'ex_date', 
        'pay_date', 'adj_date', 'report_date', 'create_date', 'update_date', 
        'publish_date', 'release_date', 'begin_date', 'finish_date', 'expire_date', 
        'apply_date', 'reg_date', 'issue_date', 'maturity_date', 'settle_date', 
        'clear_date', 'open_date', 'close_date', 'suspend_date', 'resume_date', 
        'cancel_date', 'complete_date', 'confirm_date', 'modify_date', 'submit_date', 
        'audit_date', 'approve_date', 'sign_date', 'effective_date', 'expiry_date', 
        'birth_date', 'death_date', 'event_date', 'action_date', 'oper_date', 
        'trans_date', 'value_date', 'booking_date', 'delivery_date', 'pickup_date', 
        'return_date', 'due_date', 'payment_date', 'billing_date', 'cycle_date', 
        'term_date', 'start_period', 'end_period', 'from_date', 'to_date', 
        'first_date', 'last_date', 'prev_date', 'next_date', 'init_date', 
        'final_date', 'base_date', 'ref_date', 'sys_date', 'work_date', 
        'holiday_date', 'business_date', 'calendar_date', 'snapshot_date', 
        'asof_date', 'tradedate', 'pubdate', 'enddate', 'begindate', 'opendate', 
        'closedate', 'listdate', 'delistdate', 'exdate', 'paydate', 'adjdate', 
        'reportdate', 'createdate', 'updatedate', 'publishdate', 'releasedate', 
        'begindate', 'finishdate', 'expiredate', 'applydate', 'regdate', 
        'issuedate', 'maturitydate', 'settledate', 'canceldate', 'completedate', 
        'confirmdat', 'modifydate', 'submitdate', 'auditdate', 'approvedate', 
        'signdate', 'effectivedate', 'expirydate', 'birthdate', 'deathdate', 
        'eventdate', 'actiondate', 'operdate', 'transdate', 'valuedate', 
        'bookingdate', 'deliverydate', 'pickupdate', 'returndate', 'duedate', 
        'paymentdate', 'billingdate', 'cycledate', 'termdate'
    }
    
    # 定义非日期参数列表
    non_date_params = {
        'ts_code', 'code', 'symbol', 'sec_code', 'security_code', 'stock_code', 
        'fund_code', 'index_code', 'exchange', 'market', 'asset', 'freq', 'adj', 
        'ma', 'factors', 'list_status', 'asset_type', 'industry', 'area', 
        'market_type', 'trade_type', 'vol', 'amount', 'name', 'type', 'status', 
        'source', 'category', 'level', 'grade', 'class', 'style', 'method', 
        'mode', 'format', 'unit', 'currency', 'lang', 'version', 'fields', 
        'columns', 'orderby', 'order', 'sort', 'limit', 'offset', 'page', 'size', 
        'key', 'token', 'api_key', 'user_id', 'client_id', 'password', 'secret', 
        'region', 'province', 'city', 'address', 'zip', 'email', 'phone', 
        'mobile', 'fax', 'url', 'host', 'port', 'path', 'query', 'body', 'header', 
        'cookie', 'session', 'auth', 'authorization', 'access_token', 
        'refresh_token', 'client_secret', 'api_secret', 'app_id', 'app_secret', 
        'consumer_key', 'consumer_secret', 'oauth_token', 'oauth_token_secret', 
        'bearer_token', 'jwt_token', 'cert', 'key_file', 'cert_file', 'ca_cert', 
        'ssl_cert', 'ssl_key', 'ssl_ca', 'timeout', 'retries', 'delay', 'backoff', 
        'max_retries', 'retry_delay', 'retry_backoff', 'retry_on_status', 
        'retry_on_exception', 'retry_on_timeout', 'retry_on_error', 'retry_on_failure', 
        'retry_on_rate_limit', 'retry_on_connection_error', 'retry_on_server_error', 
        'retry_on_client_error', 'retry_on_network_error', 'retry_on_temporary_error', 
        'retry_on_transient_error', 'retry_on_permanent_error', 'retry_on_unknown_error', 
        'retry_on_timeout_error', 'retry_on_connection_timeout', 'retry_on_read_timeout', 
        'retry_on_write_timeout', 'retry_on_operation_timeout', 'retry_on_request_timeout', 
        'retry_on_response_timeout', 'retry_on_api_timeout', 'retry_on_service_timeout', 
        'retry_on_system_timeout', 'retry_on_network_timeout', 'retry_on_dns_timeout', 
        'retry_on_ssl_timeout', 'retry_on_handshake_timeout', 'retry_on_connect_timeout', 
        'retry_on_accept_timeout', 'retry_on_send_timeout', 'retry_on_receive_timeout', 
        'retry_on_data_timeout', 'retry_on_idle_timeout', 'retry_on_keepalive_timeout', 
        'retry_on_linger_timeout', 'retry_on_select_timeout', 'retry_on_poll_timeout', 
        'retry_on_epoll_timeout', 'retry_on_kqueue_timeout', 'retry_on_aio_timeout', 
        'retry_on_async_timeout', 'retry_on_sync_timeout', 'retry_on_block_timeout', 
        'retry_on_nonblock_timeout', 'retry_on_socket_timeout', 'retry_on_http_timeout', 
        'retry_on_tcp_timeout', 'retry_on_udp_timeout', 'retry_on_ip_timeout', 
        'retry_on_ethernet_timeout', 'retry_on_link_timeout', 'retry_on_physical_timeout', 
        'retry_on_transport_timeout', 'retry_on_session_timeout', 'retry_on_presentation_timeout', 
        'retry_on_application_timeout', 'retry_on_network_layer_timeout', 
        'retry_on_data_link_layer_timeout', 'retry_on_physical_layer_timeout', 
        'retry_on_transport_layer_timeout', 'retry_on_session_layer_timeout', 
        'retry_on_presentation_layer_timeout', 'retry_on_application_layer_timeout', 
        'retry_on_network_protocol_timeout', 'retry_on_data_link_protocol_timeout', 
        'retry_on_physical_protocol_timeout', 'retry_on_transport_protocol_timeout', 
        'retry_on_session_protocol_timeout', 'retry_on_presentation_protocol_timeout', 
        'retry_on_application_protocol_timeout', 'retry_on_application_layer_protocol_timeout', 
        'retry_on_presentation_layer_protocol_timeout', 'retry_on_session_layer_protocol_timeout', 
        'retry_on_transport_layer_protocol_timeout', 'retry_on_network_layer_protocol_timeout', 
        'retry_on_data_link_layer_protocol_timeout', 'retry_on_physical_layer_protocol_timeout'
    }
    
    # 检查是否只包含日期参数
    has_date_param = any(param in date_params for param in param_names)
    has_non_date_param = any(param in non_date_params for param in param_names)
    
    is_date_only = has_date_param and not has_non_date_param
    
    return param_names, is_date_only

def main():
    config_dir = Path('/home/quan/testdata/aspipe_v4/app4/config/interfaces')
    date_param_interfaces = []

    for yaml_file in config_dir.glob('*.yaml'):
        param_names, is_date_only = analyze_interface_params(yaml_file)

        # 检查是否包含日期参数（start_date, end_date, trade_date等）
        date_params = {
            'start_date', 'end_date', 'trade_date', 'ann_date', 'period', 'month',
            'date', 'pub_date', 'due_date', 'list_date', 'delist_date', 'ex_date',
            'pay_date', 'adj_date', 'report_date', 'create_date', 'update_date',
            'publish_date', 'release_date', 'begin_date', 'finish_date', 'expire_date',
            'apply_date', 'reg_date', 'issue_date', 'maturity_date', 'settle_date',
            'clear_date', 'open_date', 'close_date', 'suspend_date', 'resume_date',
            'cancel_date', 'complete_date', 'confirm_date', 'modify_date', 'submit_date',
            'audit_date', 'approve_date', 'sign_date', 'effective_date', 'expiry_date',
            'birth_date', 'death_date', 'event_date', 'action_date', 'oper_date',
            'trans_date', 'value_date', 'booking_date', 'delivery_date', 'pickup_date',
            'return_date', 'due_date', 'payment_date', 'billing_date', 'cycle_date',
            'term_date', 'start_period', 'end_period', 'from_date', 'to_date',
            'first_date', 'last_date', 'prev_date', 'next_date', 'init_date',
            'final_date', 'base_date', 'ref_date', 'sys_date', 'work_date',
            'holiday_date', 'business_date', 'calendar_date', 'snapshot_date',
            'asof_date', 'tradedate', 'pubdate', 'enddate', 'begindate', 'opendate',
            'closedate', 'listdate', 'delistdate', 'exdate', 'paydate', 'adjdate',
            'reportdate', 'createdate', 'updatedate', 'publishdate', 'releasedate',
            'begindate', 'finishdate', 'expiredate', 'applydate', 'regdate',
            'issuedate', 'maturitydate', 'settledate', 'canceldate', 'completedate',
            'confirmdat', 'modifydate', 'submitdate', 'auditdate', 'approvedate',
            'signdate', 'effectivedate', 'expirydate', 'birthdate', 'deathdate',
            'eventdate', 'actiondate', 'operdate', 'transdate', 'valuedate',
            'bookingdate', 'deliverydate', 'pickupdate', 'returndate', 'duedate',
            'paymentdate', 'billingdate', 'cycledate', 'termdate'
        }

        has_date_param = any(param in date_params for param in param_names)

        if has_date_param:
            interface_name = yaml_file.stem
            date_param_interfaces.append(interface_name)
            print(f"Found interface with date params: {interface_name} with params: {param_names}")

    print(f"\nTotal interfaces with date parameters found: {len(date_param_interfaces)}")
    print("Interfaces with date parameters:")
    for interface in date_param_interfaces:
        print(f"  - {interface}")

    # 将结果写入文件
    output_dir = Path('/home/quan/testdata/aspipe_v4/p/2026-1-2')
    output_file = output_dir / 'date_param_interfaces.txt'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Interfaces that use date parameters:\n")
        f.write("====================================\n")
        for interface in date_param_interfaces:
            f.write(f"{interface}\n")

    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()