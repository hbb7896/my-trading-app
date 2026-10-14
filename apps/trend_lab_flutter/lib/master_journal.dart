import 'package:flutter/material.dart';

import 'master_reference.dart';
import 'master_metrics.dart';
import 'trade.dart';
import 'trading_master.dart' show mistakeTags;

class MasterJournalPage extends StatefulWidget {
  final Trade trade;
  final Future<void> Function(Trade) onSave;
  final VoidCallback onBack;
  final ValueChanged<Trade> onEdit;
  const MasterJournalPage({
    super.key,
    required this.trade,
    required this.onSave,
    required this.onBack,
    required this.onEdit,
  });
  @override
  State<MasterJournalPage> createState() => _MasterJournalPageState();
}

class _MasterJournalPageState extends State<MasterJournalPage> {
  late final TextEditingController memo, chart, emotion, discipline;
  late List<String> tags;
  late String baseline;
  bool busy = false, saved = false;
  String? error;
  bool get sample => widget.trade.id.startsWith('DEMO_');
  String get signature => [
    memo.text,
    chart.text,
    emotion.text,
    discipline.text,
    tags.join('\u0000'),
  ].join('\u0001');
  @override
  void initState() {
    super.initState();
    final t = widget.trade;
    memo = TextEditingController(text: t.memo);
    chart = TextEditingController(text: t.extra['chart_link'] as String? ?? '');
    emotion = TextEditingController(text: t.extra['emotion'] as String? ?? '');
    discipline = TextEditingController(
      text: t.extra['discipline'] as String? ?? '',
    );
    tags = List<String>.from(t.extra['tags'] as List? ?? []);
    baseline = signature;
    for (final c in [memo, chart, emotion, discipline]) {
      c.addListener(changed);
    }
  }

  void changed() {
    setState(() => saved = false);
  }

  @override
  void dispose() {
    for (final c in [memo, chart, emotion, discipline]) {
      c.removeListener(changed);
      c.dispose();
    }
    super.dispose();
  }

  Future<bool> leave() async {
    if (signature == baseline) return true;
    return await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
            title: const Text('저장하지 않은 복기 내용'),
            content: const Text('변경 내용을 저장하지 않고 나갈까요?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('계속 작성'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('나가기'),
              ),
            ],
          ),
        ) ==
        true;
  }

  Future<void> save() async {
    final uri = Uri.tryParse(chart.text.trim());
    if (chart.text.trim().isNotEmpty &&
        (uri == null ||
            !['http', 'https'].contains(uri.scheme) ||
            uri.host.isEmpty ||
            uri.userInfo.isNotEmpty)) {
      setState(() => error = '차트는 http 또는 https 이미지 주소를 입력해주세요.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
      saved = false;
    });
    final t = widget.trade;
    try {
      await widget.onSave(
        Trade(
          id: t.id,
          ticker: t.ticker,
          code: t.code,
          entry: t.entry,
          exit: t.exit,
          buy: t.buy,
          sell: t.sell,
          memo: memo.text,
          extra: {
            ...t.extra,
            'tags': tags,
            'chart_link': chart.text.trim(),
            'emotion': emotion.text,
            'discipline': discipline.text,
          },
        ),
      );
      if (mounted) {
        setState(() {
          baseline = signature;
          saved = true;
        });
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
  Widget build(BuildContext context) {
    final t = widget.trade, link = t.extra['chart_link'] as String? ?? '';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 18,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            OutlinedButton.icon(
              onPressed: busy
                  ? null
                  : () async {
                      if (await leave()) {
                        widget.onBack();
                      }
                    },
              icon: const Icon(Icons.arrow_back, size: 17),
              label: const Text('대시보드로 돌아가기'),
            ),
            muted(
              sample
                  ? '샘플 거래 · 저장할 수 없습니다'
                  : signature != baseline
                  ? '저장하지 않은 변경사항'
                  : saved
                  ? '복기 저장 완료'
                  : '대시보드 거래에 연결된 일지',
            ),
          ],
        ),
        const SizedBox(height: 22),
        MasterPanel(
          title: '${t.ticker} 매매일지',
          caption:
              '${t.entry.isEmpty ? '진입일 미입력' : t.entry} · ${t.exit} 청산${holding(t) == null ? '' : ' · ${holding(t)}일 보유'}',
          action: sample
              ? null
              : IconButton(
                  tooltip: '거래 정보 수정',
                  onPressed: () async {
                    if (await leave()) {
                      widget.onEdit(t);
                    }
                  },
                  icon: const Icon(Icons.edit_outlined),
                ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: cardGrid([
              MasterCard(label: '매수 금액', value: masterWon(t.buy)),
              MasterCard(label: '매도 금액', value: masterWon(t.sell)),
              MasterCard(
                label: '실현 손익',
                value: '${t.pnl > 0 ? '+' : ''}${masterWon(t.pnl)}',
                color: masterSign(t.pnl),
              ),
              MasterCard(
                label: '수익률',
                value: masterPct(t.roi),
                color: masterSign(t.roi),
              ),
            ]),
          ),
        ),
        pair(
          MasterPanel(
            title: '매매 차트',
            caption: '진입과 청산 지점을 확인하며 복기하세요.',
            action: const Icon(Icons.image_outlined, color: masterMint),
            child: link.isEmpty
                ? SizedBox(
                    height: 420,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(
                          Icons.image_outlined,
                          size: 42,
                          color: masterMuted,
                        ),
                        const SizedBox(height: 18),
                        const Text('차트를 첨부해보세요'),
                        Padding(
                          padding: const EdgeInsets.all(22),
                          child: muted(
                            '차트 이미지 링크를 입력하고 복기 내용을 저장하면 여기에 표시됩니다.',
                          ),
                        ),
                      ],
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.all(16),
                    child: Image.network(
                      link,
                      fit: BoxFit.contain,
                      errorBuilder: (_, e, s) => SizedBox(
                        height: 360,
                        child: Center(
                          child: muted(
                            '차트를 불러오지 못했습니다. 접근 가능한 이미지 주소인지 확인해주세요.',
                          ),
                        ),
                      ),
                    ),
                  ),
          ),
          MasterPanel(
            title: '매매 복기',
            caption: '잘한 점과 다음 거래에서 개선할 점을 기록하세요.',
            action: const Icon(Icons.menu_book_outlined, color: masterMint),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(22, 0, 22, 22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: memo,
                    enabled: !sample && !busy,
                    maxLines: 9,
                    maxLength: 10000,
                    decoration: const InputDecoration(
                      labelText: '메모 및 상세 복기',
                      hintText: '진입 근거, 청산 이유, 원칙을 지킨 부분과 개선할 점',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: chart,
                    enabled: !sample && !busy,
                    maxLength: 2048,
                    decoration: const InputDecoration(
                      labelText: '차트 이미지 링크',
                      hintText: 'https://…/chart.png',
                    ),
                  ),
                  muted('이미지의 직접 링크를 붙여넣어주세요.', size: 12),
                  const SizedBox(height: 16),
                  const Text('실수 태그'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final tag in {...mistakeTags, ...tags})
                        FilterChip(
                          label: Text(
                            tag,
                            style: const TextStyle(fontSize: 12),
                          ),
                          selected: tags.contains(tag),
                          onSelected: sample || busy
                              ? null
                              : (v) => setState(() {
                                  saved = false;
                                  if (v) {
                                    tags.add(tag);
                                  } else {
                                    tags.remove(tag);
                                  }
                                }),
                        ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  TextField(
                    controller: emotion,
                    enabled: !sample && !busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: '심리 상태',
                      hintText: '예: 차분함',
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: discipline,
                    enabled: !sample && !busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: '규율 준수 여부',
                      hintText: '예: 손절 원칙 준수',
                    ),
                  ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Text(
                        error!,
                        style: const TextStyle(color: masterRed),
                      ),
                    ),
                  if (saved)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Text(
                        '✓ 복기 내용을 저장했습니다.',
                        style: TextStyle(color: masterMint),
                      ),
                    ),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: sample || busy ? null : save,
                      icon: const Icon(Icons.check, size: 17),
                      label: Text(
                        busy
                            ? '저장 중…'
                            : sample
                            ? '샘플 거래는 저장할 수 없습니다'
                            : '매매일지 저장',
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          left: 1,
        ),
      ],
    );
  }
}

class MasterTradeForm extends StatefulWidget {
  final Trade? trade;
  final Future<void> Function(Trade)? onDelete;
  const MasterTradeForm({super.key, this.trade, this.onDelete});
  @override
  State<MasterTradeForm> createState() => _MasterTradeFormState();
}

class _MasterTradeFormState extends State<MasterTradeForm> {
  final form = GlobalKey<FormState>();
  late final List<TextEditingController> c;
  late List<String> tags;
  @override
  void initState() {
    super.initState();
    final t = widget.trade;
    final today = DateTime.now()
        .toUtc()
        .add(const Duration(hours: 9))
        .toIso8601String()
        .substring(0, 10);
    c = [
      t?.ticker ?? '',
      t?.entry ?? today,
      t?.exit ?? today,
      t?.buy.toString() ?? '',
      t?.sell.toString() ?? '',
      t?.memo ?? '',
      t?.code ?? '',
    ].map((s) => TextEditingController(text: s)).toList();
    tags = List<String>.from(t?.extra['tags'] as List? ?? []);
  }

  @override
  void dispose() {
    for (final x in c) {
      x.dispose();
    }
    super.dispose();
  }

  bool date(String s) {
    final d = DateTime.tryParse(s);
    return RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(s) &&
        d != null &&
        d.toIso8601String().substring(0, 10) == s;
  }

  Widget field(int i, String label) => TextFormField(
    controller: c[i],
    maxLines: i == 5 ? 3 : 1,
    maxLength: i == 5 ? 10000 : null,
    keyboardType: i == 3 || i == 4
        ? const TextInputType.numberWithOptions(decimal: true)
        : TextInputType.text,
    decoration: InputDecoration(labelText: label),
    onChanged: (_) => setState(() {}),
    validator: (s) {
      final v = s?.trim() ?? '';
      if (i == 0 && (v.isEmpty || v.length > 100)) return '종목명을 입력하세요.';
      if (i == 1 && v.isNotEmpty && !date(v) || i == 2 && !date(v)) {
        return '올바른 날짜를 입력하세요.';
      }
      if (i == 2 && c[1].text.isNotEmpty && v.compareTo(c[1].text.trim()) < 0) {
        return '청산일은 진입일 이후여야 합니다.';
      }
      if (i == 3 || i == 4) {
        final n = double.tryParse(v);
        if (n == null || !n.isFinite || n < 0 || n > 1e15 || (i == 3 && n == 0)) {
          return '올바른 금액을 입력하세요.';
        }
      }
      if (i == 6 && v.isNotEmpty && !RegExp(r'^\d{6}$').hasMatch(v)) {
        return '6자리 종목코드를 입력하세요.';
      }
      return null;
    },
  );
  @override
  Widget build(BuildContext context) {
    final buy = double.tryParse(c[3].text) ?? 0,
        sell = double.tryParse(c[4].text) ?? 0,
        pnl = sell - buy;
    return AlertDialog(
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'TRADE JOURNAL',
            style: TextStyle(
              color: masterMint,
              fontSize: 11,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 8),
          Text(widget.trade == null ? '새 거래 등록' : '거래 수정'),
          const SizedBox(height: 8),
          muted('매매의 결과와 과정을 함께 기록하세요.'),
        ],
      ),
      content: SizedBox(
        width: 570,
        child: SingleChildScrollView(
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                field(0, '종목명'),
                const SizedBox(height: 18),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: field(1, '매수 진입일 (선택)')),
                    const SizedBox(width: 14),
                    Expanded(child: field(2, '매도 청산일')),
                  ],
                ),
                const SizedBox(height: 18),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: field(3, '총 매수금액 (원)')),
                    const SizedBox(width: 14),
                    Expanded(child: field(4, '총 매도금액 (원)')),
                  ],
                ),
                const SizedBox(height: 18),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  color: const Color(0xff24313e),
                  child: Text(
                    '실현 손익 ${masterWon(pnl)} · 수익률 ${masterPct(buy > 0 ? pnl / buy * 100 : 0)}',
                    style: TextStyle(color: masterSign(pnl)),
                  ),
                ),
                const SizedBox(height: 20),
                const Text('실수 태그'),
                muted('정상 거래라면 선택하지 마세요.', size: 12),
                Wrap(
                  spacing: 6,
                  children: [
                    for (final tag in {...mistakeTags, ...tags})
                      FilterChip(
                        label: Text(tag, style: const TextStyle(fontSize: 12)),
                        selected: tags.contains(tag),
                        onSelected: (v) => setState(() {
                          if (v) {
                            tags.add(tag);
                          } else {
                            tags.remove(tag);
                          }
                        }),
                      ),
                  ],
                ),
                const SizedBox(height: 18),
                field(5, '복기 메모'),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: muted('종목코드 (차트 복기 시 선택 입력)', size: 12),
                  children: [field(6, '6자리 종목코드')],
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        if (widget.trade != null && widget.onDelete != null)
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await widget.onDelete!(widget.trade!);
            },
            child: const Text('삭제', style: TextStyle(color: masterRed)),
          ),
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('취소'),
        ),
        FilledButton.icon(
          onPressed: () {
            if (!form.currentState!.validate()) return;
            final t = widget.trade;
            Navigator.pop(
              context,
              Trade(
                id: t?.id ?? '',
                ticker: c[0].text.trim(),
                code: c[6].text.trim(),
                entry: c[1].text.trim(),
                exit: c[2].text.trim(),
                buy: double.parse(c[3].text),
                sell: double.parse(c[4].text),
                memo: c[5].text,
                extra: {...t?.extra ?? {}, 'tags': tags},
              ),
            );
          },
          icon: const Icon(Icons.check, size: 16),
          label: const Text('거래 저장'),
        ),
      ],
    );
  }
}
