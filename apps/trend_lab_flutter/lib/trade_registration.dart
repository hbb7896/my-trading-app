import 'package:flutter/material.dart';

import 'api.dart';
import 'trade.dart';
import 'capital_accounts.dart';
import 'master_journal.dart';
import 'master_reference.dart';

class TradeRegistrationResult {
  final String? cycleId, accountId;
  final Trade? completed;
  const TradeRegistrationResult({this.cycleId, this.accountId, this.completed});
}

/// The single entry point for new purchases and historical completed trades.
class TradeRegistrationDialog extends StatefulWidget {
  final TradingApi api;
  final String? initialAccountId;
  const TradeRegistrationDialog({
    super.key,
    required this.api,
    this.initialAccountId,
  });
  @override
  State<TradeRegistrationDialog> createState() =>
      _TradeRegistrationDialogState();
}

class _TradeRegistrationDialogState extends State<TradeRegistrationDialog> {
  List<Map<String, dynamic>>? accounts;
  String? error;
  late String accountId = widget.initialAccountId ?? 'isa';
  String completedAccount = 'none';
  bool historical = false, busy = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await widget.api.request('/api/positions');
      if (mounted) {
        setState(() {
          accounts = (result['accounts'] as List).cast<Map<String, dynamic>>();
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  Widget controls() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Text('거래 등록'),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          ChoiceChip(
            label: const Text('새 매수 · 보유 관리'),
            selected: !historical,
            onSelected: busy ? null : (_) => setState(() => historical = false),
          ),
          ChoiceChip(
            label: const Text('지난 청산 거래'),
            selected: historical,
            onSelected: busy ? null : (_) => setState(() => historical = true),
          ),
        ],
      ),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(
        key: ValueKey('account-$historical'),
        initialValue: historical ? completedAccount : accountId,
        isExpanded: true,
        decoration: const InputDecoration(labelText: '계좌'),
        items: [
          if (historical)
            const DropdownMenuItem(value: 'none', child: Text('계좌 미분류')),
          for (final a in accounts!)
            DropdownMenuItem(
              value: a['id'] as String,
              child: Text(a['name'] as String),
            ),
        ],
        onChanged: busy
            ? null
            : (v) => setState(() {
                if (historical) {
                  completedAccount = v!;
                } else {
                  accountId = v!;
                }
              }),
      ),
      const SizedBox(height: 10),
      muted(
        historical
            ? '이미 끝난 거래를 금액 합계로 기록합니다. 보유 수량과 R은 추정하지 않습니다. 보유 관리한 거래는 청산 시 자동 등록되므로 다시 입력하지 않아도 됩니다.'
            : '최초 매수를 한 번 등록하면 보유 포지션으로 관리되고, 최종 청산 시 거래 기록·매매일지에 자동 연결됩니다.',
        size: 12,
      ),
    ],
  );
  Future<void> purchase(Map<String, dynamic> values) async {
    final id = 'C_${values['actionId']}';
    final response = await widget.api.request(
      '/api/positions/$id/action',
      method: 'POST',
      body: {...values, 'type': 'buy', 'version': 0},
    );
    if (mounted) {
      Navigator.pop(
        context,
        TradeRegistrationResult(
          cycleId: response['id'] as String,
          accountId: response['accountId'] as String,
        ),
      );
    }
  }

  Future<void> completed(Trade value) async {
    final response = await widget.api.request(
      '/api/trades',
      method: 'POST',
      body: {
        ...value.toJson(),
        if (completedAccount != 'none') 'account_id': completedAccount,
      },
    );
    if (mounted) {
      Navigator.pop(
        context,
        TradeRegistrationResult(
          completed: Trade.fromJson(Map<String, dynamic>.from(response)),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (accounts == null) {
      return AlertDialog(
        title: const Text('거래 등록'),
        content: error == null ? const LinearProgressIndicator() : Text(error!),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('취소'),
          ),
          if (error != null)
            TextButton(onPressed: load, child: const Text('다시 불러오기')),
        ],
      );
    }
    final account = accounts!.where((a) => a['id'] == accountId).first;
    return Stack(
      children: [
        Offstage(
          offstage: historical,
          child: ExcludeFocus(
            excluding: historical,
            child: account['plan'] == null
                ? AlertDialog(
                    title: controls(),
                    content: const Text(
                      '이 계좌의 기준 자금을 먼저 설정하세요. 포지션 R·CR·E → 계좌별 금액 설정에서 저장할 수 있습니다.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('닫기'),
                      ),
                    ],
                  )
                : CapitalBuyDialog(
                    api: widget.api,
                    account: account,
                    registrationHeader: controls(),
                    closeAfterSave: false,
                    onBusyChanged: (v) {
                      if (mounted) setState(() => busy = v);
                    },
                    onSave: purchase,
                  ),
          ),
        ),
        Offstage(
          offstage: !historical,
          child: ExcludeFocus(
            excluding: !historical,
            child: MasterTradeForm(
              registrationHeader: controls(),
              onSave: completed,
              onBusyChanged: (v) {
                if (mounted) setState(() => busy = v);
              },
            ),
          ),
        ),
      ],
    );
  }
}
