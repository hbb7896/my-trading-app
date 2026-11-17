import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'master_reference.dart';
import 'position_risk.dart' show riskValue;

class OpenPositionsPanel extends StatefulWidget {
  final TradingApi? api;
  final String query;
  final ValueChanged<String> onOpen;
  const OpenPositionsPanel({
    super.key,
    this.api,
    this.query = '',
    required this.onOpen,
  });
  @override
  State<OpenPositionsPanel> createState() => _OpenPositionsPanelState();
}

class _OpenPositionsPanelState extends State<OpenPositionsPanel> {
  List<Map<String, dynamic>> rows = [];
  String? error;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    widget.api?.addListener(load);
    timer = Timer.periodic(const Duration(seconds: 30), (_) => load());
    load();
  }

  @override
  void dispose() {
    timer?.cancel();
    widget.api?.removeListener(load);
    super.dispose();
  }

  Future<void> load() async {
    if (widget.api == null) return;
    try {
      final result = await widget.api!.request('/api/positions');
      if (mounted) {
        setState(() {
          rows = (result['cycles'] as List)
              .cast<Map<String, dynamic>>()
              .where((r) => r['closed'] == false)
              .toList();
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final visible = rows
        .where(
          (r) => ('${r['ticker']} ${r['code']} ${r['accountName']}')
              .toLowerCase()
              .contains(widget.query.toLowerCase()),
        )
        .toList();
    return MasterPanel(
      title: '보유 중인 거래 · ${visible.length}건',
      caption: '새 매수는 여기에 표시됩니다. 선택하면 추가 매수·부분 매도·손절 관리로 이동합니다. 아래 청산 기록과 중복 집계하지 않습니다.',
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (error != null)
              Text(error!, style: const TextStyle(color: masterRed)),
            for (final r in visible)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${r['ticker']} · ${r['accountName']}'),
                subtitle: Text(
                  '보유 ${r['quantity']}주 · ${riskValue(r['totalR'])} · CR ${riskValue(r['cr'], '')} · E ${riskValue(r['e'], '')}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => widget.onOpen(r['id'] as String),
              ),
            if (visible.isEmpty) muted('기록된 보유 거래가 없습니다. 거래 등록에서 새 매수를 입력하세요.'),
          ],
        ),
      ),
    );
  }
}
