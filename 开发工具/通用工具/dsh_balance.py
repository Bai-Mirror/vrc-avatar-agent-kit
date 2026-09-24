#!/usr/bin/env python3
"""【项目沉淀】通用工具
适用素体：无关；相关素材：无；可复用性：★★★
用途：只读查询 DSH 实际凭据的余额；不显示密钥、不消费模型额度。

退出码：0 可继续，2 查询/数据不可信，3 触及储备线，4 账户不可用。
储备线（CNY）取 --reserve-cny，缺省读 DSH_RESERVE_CNY（环境变量 > kit.env），都没有时用 30；
不换算或合并不同币种余额。
与 dsh_task.js 一致：忽略环境中的 DEEPSEEK_API_KEY 和 DSH_HOME。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_env  # noqa: E402  读 <工作区>/kit.env（环境变量优先）


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reserve-cny', type=Decimal, default=None)
    args = parser.parse_args()
    if args.reserve_cny is None:
        try:
            args.reserve_cny = Decimal(kit_env.get('DSH_RESERVE_CNY', '') or '30')
        except InvalidOperation:
            parser.error('DSH_RESERVE_CNY 不是数值')
    if not args.reserve_cny.is_finite() or args.reserve_cny < 0:
        parser.error('储备线必须是非负有限数值')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'reserve_cny': str(args.reserve_cny), 'status': 'unknown'}
    try:
        credentials = yaml.safe_load((Path.home() / '.dsh/.credentials.yaml').read_text())
        key = credentials['refs']['DEEPSEEK_API_KEY']
        if not isinstance(key, str) or not key.startswith('sk-'):
            raise ValueError('unsupported credentials')
        request = urllib.request.Request('https://api.deepseek.com/user/balance',
                                         headers={'Authorization': 'Bearer ' + key})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        if type(data.get('is_available')) is not bool:
            raise ValueError('invalid availability')
        balances = []
        for row in data['balance_infos']:
            currency = row['currency']
            if currency not in ('CNY', 'USD'):
                raise ValueError('unsupported currency')
            balance = {'currency': currency}
            for field in ('total_balance', 'granted_balance', 'topped_up_balance'):
                number = Decimal(str(row[field]))
                if not number.is_finite():
                    raise ValueError('invalid balance')
                balance[field] = str(number)
            balances.append(balance)
        if len({row['currency'] for row in balances}) != len(balances):
            raise ValueError('duplicate currency')
        report.update(is_available=data['is_available'], balance_infos=balances)
        cny = next((Decimal(row['total_balance']) for row in balances if row['currency'] == 'CNY'), None)
        if not data['is_available']:
            report['status'], code = 'unavailable', 4
        elif cny is None:
            report['status'], code = 'unknown', 2
        elif cny <= args.reserve_cny:
            report['status'], code = 'low', 3
        else:
            report['status'], code = 'ready', 0
    except urllib.error.HTTPError as error:
        report['error'] = 'HTTP_' + str(error.code)
        code = 2
    except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError, InvalidOperation, yaml.YAMLError) as error:
        # Never print exception text, response bodies, or credential content.
        report['error'] = type(error).__name__
        code = 2
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
