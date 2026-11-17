import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'master_reference.dart';
import 'journal_tags.dart';

String planWon(num value) {
  final parts = value
      .toStringAsFixed(6)
      .replaceFirst(RegExp(r'\.?0+$'), '')
      .split('.');
  final whole = parts[0].replaceAllMapped(
    RegExp(r'(\d)(?=(\d{3})+(?!\d))'),
    (m) => '${m[1]},',
  );
  return '$whole${parts.length > 1 ? '.${parts[1]}' : ''}원';
}

class CapitalAccountsPanel extends StatefulWidget {
  final TradingApi api;
  final List<Map<String, dynamic>> accounts;
  final Future<void> Function() onSaved;
  const CapitalAccountsPanel({
    super.key,
    required this.api,
    required this.accounts,
    required this.onSaved,
  });
  @override
  State<CapitalAccountsPanel> createState() => _CapitalAccountsPanelState();
}

class _CapitalAccountsPanelState extends State<CapitalAccountsPanel> {
  final Map<String, TextEditingController> funds = {};
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    for (final a in widget.accounts) {
      funds[a['id'] as String] = TextEditingController(
        text: a['capital'] as String? ?? '',
      )..addListener(changed);
    }
  }

  void changed() => setState(() {});
  @override
  void dispose() {
    for (final c in funds.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> save() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.request(
        '/api/positions/accounts',
        method: 'PUT',
        body: {
          'accounts': [
            for (final a in widget.accounts)
              {'id': a['id'], 'capital': funds[a['id']]!.text},
          ],
        },
      );
      await widget.onSaved();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('계좌 자금을 저장했습니다. 새 매매부터 적용됩니다.')),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => MasterPanel(
    title: '계좌별 기준 자금',
    caption:
        '금액만 입력하세요. 1E=25% · 1R=1.25% · 1유닛=6.25% · 유닛 위험=0.3125% · 기본 손절 −5%',
    child: Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final a in widget.accounts)
            Padding(
              padding: const EdgeInsets.only(bottom: 20),
              child: Builder(
                builder: (context) {
                  final amount = num.tryParse(funds[a['id']]!.text);
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextField(
                        controller: funds[a['id']],
                        enabled: !busy,
                        keyboardType: TextInputType.number,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                        ],
                        decoration: InputDecoration(
                          labelText: '${a['name']} 기준 자금',
                          suffixText: '원',
                          hintText: '기준 자금을 입력하세요',
                        ),
                      ),
                      const SizedBox(height: 10),
                      if (amount != null &&
                          amount > 0 &&
                          amount <= 1000000000000)
                        Wrap(
                          spacing: 18,
                          runSpacing: 6,
                          children: [
                            Text('1E ${planWon(amount / 4)}'),
                            Text('1R ${planWon(amount / 80)}'),
                            Text('1유닛 ${planWon(amount / 16)}'),
                            Text('유닛 위험 ${planWon(amount / 320)}'),
                          ],
                        )
                      else
                        muted('자금을 입력하면 네 가지 기준금액을 자동 계산합니다.'),
                    ],
                  );
                },
              ),
            ),
          muted(
            '1E=4유닛이며, 처음에는 1유닛부터 진입합니다. 계좌 자금을 바꿔도 이미 시작한 매매의 R·E 기준은 유지됩니다.',
          ),
          if (error != null)
            Text(error!, style: const TextStyle(color: masterRed)),
          const SizedBox(height: 10),
          FilledButton(
            onPressed: busy ? null : save,
            child: Text(busy ? '저장 중…' : '계좌 자금 저장'),
          ),
        ],
      ),
    ),
  );
}

class CapitalBuyDialog extends StatefulWidget {
  final TradingApi api;
  final Map<String, dynamic> account;
  final Map<String, dynamic>? cycle;
  final Future<void> Function(Map<String, dynamic>) onSave;
  final Widget? registrationHeader;
  final bool closeAfterSave;
  final ValueChanged<bool>? onBusyChanged;
  const CapitalBuyDialog({
    super.key,
    required this.api,
    required this.account,
    this.cycle,
    required this.onSave,
    this.registrationHeader,
    this.closeAfterSave = true,
    this.onBusyChanged,
  });
  @override
  State<CapitalBuyDialog> createState() => _CapitalBuyDialogState();
}

class _CapitalBuyDialogState extends State<CapitalBuyDialog> {
  final ticker = TextEditingController(),
      code = TextEditingController(),
      price = TextEditingController(),
      shares = TextEditingController(),
      stop = TextEditingController(),
      fee = TextEditingController(text: '0'),
      memo = TextEditingController(),
      at = TextEditingController(
        text: DateTime.now().toUtc().toIso8601String(),
      );
  late final String orderId = 'A_${DateTime.now().microsecondsSinceEpoch}';
  Timer? timer;
  int sequence = 0;
  bool busy = false;
  String? error;
  Map<String, dynamic>? suggestion;
  final Set<String> tags = {};
  @override
  void didUpdateWidget(covariant CapitalBuyDialog oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.account['id'] != widget.account['id'] &&
        price.text.isNotEmpty) {
      sequence++;
      suggest();
    }
  }

  @override
  void initState() {
    super.initState();
    price.addListener(priceChanged);
  }

  void priceChanged() {
    timer?.cancel();
    sequence++;
    timer = Timer(const Duration(milliseconds: 300), suggest);
  }

  Future<void> suggest() async {
    if (price.text.isEmpty) return;
    final requestId = ++sequence;
    try {
      final result = Map<String, dynamic>.from(
        await widget.api.request(
          '/api/positions/unit-plan',
          method: 'POST',
          body: {
            'accountId': widget.account['id'],
            'price': price.text,
            if (widget.cycle != null) 'cycleId': widget.cycle!['id'],
          },
        ),
      );
      if (mounted && requestId == sequence) {
        setState(() {
          suggestion = result;
          shares.text = '${result['quantity']}';
          stop.text = '${result['stop']}';
          error = null;
        });
      }
    } catch (e) {
      if (mounted && requestId == sequence) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  Future<void> save() async {
    widget.onBusyChanged?.call(true);
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.onSave({
        'accountId': widget.account['id'],
        if (widget.cycle == null) 'expectedCapital': widget.account['capital'],
        'actionId': orderId,
        'at': at.text,
        'price': price.text,
        'quantity': shares.text,
        'stop': stop.text,
        'fee': fee.text,
        'memo': memo.text,
        'tags': tags.toList(),
        if (widget.cycle == null) 'ticker': ticker.text,
        if (widget.cycle == null) 'code': code.text,
      });
      if (mounted && widget.closeAfterSave) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => busy = false);
      widget.onBusyChanged?.call(false);
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    for (final c in [ticker, code, price, shares, stop, fee, memo, at]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final plan =
        (widget.cycle?['capitalPlan'] ?? widget.account['plan']) as Map;
    return AlertDialog(
      title:
          widget.registrationHeader ??
          Text(
            '${widget.account['name']} · ${widget.cycle == null ? '최초 1유닛 진입' : '추가 1유닛 매수'}',
          ),
      content: SizedBox(
        width: 480,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '1유닛 예산 ${planWon(plan['unitBudget'] as num)} · 고정 1R ${planWon(plan['oneR'] as num)}',
              ),
              muted(
                '매수가를 입력하면 예산 이내의 정수 수량과 −5% 손절가를 자동 입력합니다. 실제 체결 수량과 손절가는 수정할 수 있습니다.',
              ),
              const SizedBox(height: 14),
              for (final entry in <String, TextEditingController>{
                if (widget.cycle == null) '종목명': ticker,
                if (widget.cycle == null) '종목코드 (선택)': code,
                '매수 가격': price,
                '실제 매수 수량': shares,
                '손절가': stop,
                '수수료': fee,
                '매수 사유': memo,
                '체결 일시 (시간대 포함)': at,
              }.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: TextField(
                    controller: entry.value,
                    enabled: !busy,
                    decoration: InputDecoration(labelText: entry.key),
                    keyboardType:
                        [price, shares, stop, fee].contains(entry.value)
                        ? const TextInputType.numberWithOptions(decimal: true)
                        : TextInputType.text,
                  ),
                ),
              if (suggestion != null)
                muted(
                  '1유닛 제안 ${suggestion!['quantity']}주 · 매수금액 ${planWon(suggestion!['buyAmount'] as num)} · 예산 잔액 ${planWon(suggestion!['unusedBudget'] as num)}',
                ),
              if (suggestion?['quantity'] == 0)
                const Text(
                  '1주 가격이 1유닛 예산을 초과합니다.',
                  style: TextStyle(color: masterRed),
                ),
              const SizedBox(height: 12),
              const Text('실수 태그 (선택)'),
              muted('선택한 태그와 매수 사유는 청산 후 매매일지로 이어집니다.', size: 12),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  for (final tag in mistakeTags)
                    FilterChip(
                      label: Text(tag, style: const TextStyle(fontSize: 12)),
                      selected: tags.contains(tag),
                      onSelected: busy
                          ? null
                          : (selected) => setState(() {
                              if (selected) {
                                tags.add(tag);
                              } else {
                                tags.remove(tag);
                              }
                            }),
                    ),
                ],
              ),
              if (error != null)
                Text(error!, style: const TextStyle(color: masterRed)),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('취소'),
        ),
        FilledButton(
          onPressed: busy ? null : save,
          child: Text(busy ? '저장 중…' : '체결 저장'),
        ),
      ],
    );
  }
}
