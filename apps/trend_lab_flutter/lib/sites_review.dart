import 'dart:math' as math;
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'main.dart' show percent, money;
import 'trade.dart';
part 'sites_price_painter.dart';

const sitePanel = Color(0xff121e30),
    siteLine = Color(0xff26354b),
    siteMuted = Color(0xff91a4bd),
    siteMint = Color(0xff6fe6b9);
const averagesColors = <int, Color>{
  20: Color(0xfff2c96c),
  50: Color(0xff70a9fa),
  150: Color(0xffb29cfa),
  200: Color(0xffff8797),
};
Color sign(num n) => n >= 0 ? siteMint : const Color(0xffff818b);
Widget note(String text, {double size = 13}) => Text(
  text,
  style: TextStyle(color: siteMuted, fontSize: size, height: 1.65),
);
Widget title(String text, {double size = 17}) => Text(
  text,
  style: TextStyle(fontSize: size, fontWeight: FontWeight.w600),
);
Widget eyebrow(String text) => Padding(
  padding: const EdgeInsets.only(bottom: 8),
  child: Text(
    text,
    style: const TextStyle(
      fontSize: 11,
      color: siteMint,
      letterSpacing: 1.5,
      fontWeight: FontWeight.w600,
    ),
  ),
);
Widget pill(String text) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
  decoration: BoxDecoration(
    border: Border.all(color: siteLine),
    borderRadius: BorderRadius.circular(7),
  ),
  child: Text(text, style: const TextStyle(color: siteMint, fontSize: 12)),
);
Widget box(Widget child, {double padding = 23}) => Container(
  padding: EdgeInsets.all(padding),
  decoration: BoxDecoration(
    color: sitePanel,
    border: Border.all(color: siteLine),
    borderRadius: BorderRadius.circular(14),
  ),
  child: Material(type: MaterialType.transparency, child: child),
);
Widget foot(String text) => Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  children: [
    const Divider(height: 34, color: siteLine),
    note(text, size: 12),
  ],
);

class SitesReview extends StatefulWidget {
  final List<Trade> trades;
  final Trade? selected;
  final Map<String, dynamic>? report;
  final bool loading, analyzing, connected;
  final String? error, reviewError;
  final Future<void> Function(Trade) analyze, remove;
  final Future<void> Function(Trade?) edit;
  final Future<void> Function() refresh, importRecords, settings;
  final VoidCallback? openMaster;
  final Map<String, dynamic>? sampleData;
  const SitesReview({
    super.key,
    required this.trades,
    this.selected,
    this.report,
    required this.loading,
    required this.analyzing,
    required this.connected,
    this.error,
    this.reviewError,
    required this.analyze,
    required this.remove,
    required this.edit,
    required this.refresh,
    required this.importRecords,
    required this.settings,
    this.openMaster,
    this.sampleData,
  });
  @override
  State<SitesReview> createState() => _SitesReviewState();
}

class _SitesReviewState extends State<SitesReview> {
  final code = TextEditingController(),
      entry = TextEditingController(),
      exit = TextEditingController();
  final form = GlobalKey<FormState>();
  String? record;
  final pageScroll = ScrollController();
  Map<String, dynamic>? sample;
  bool sampleVisible = false, showEmpty = false;
  @override
  void initState() {
    super.initState();
    if (widget.sampleData != null) {
      sample = widget.sampleData;
      if (widget.connected && widget.trades.isEmpty) {
        selectSample();
      }
    } else {
      loadSample(auto: widget.connected && widget.trades.isEmpty);
    }
  }

  Future<void> loadSample({bool auto = false}) async {
    final data = jsonDecode(
      await rootBundle.loadString('assets/trend_lab_sample.json'),
    ) as Map<String, dynamic>;
    if (!mounted) {
      return;
    }
    setState(() => sample = data);
    if (auto) {
      selectSample();
    }
  }

  void selectSample() {
    if (sample == null) {
      return;
    }
    final t = sample!['trade'];
    setState(() {
      record = 'sample';
      sampleVisible = true;
      showEmpty = false;
      code.text = t['code'];
      entry.text = t['entry'];
      exit.text = t['exit'];
    });
  }

  @override
  void dispose() {
    code.dispose();
    entry.dispose();
    exit.dispose();
    pageScroll.dispose();
    super.dispose();
  }

  bool validDate(String s) {
    final d = DateTime.tryParse(s);
    return RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(s) &&
        d != null &&
        d.toIso8601String().substring(0, 10) == s;
  }

  Widget input(
    String name,
    TextEditingController c, {
    bool stock = false,
  }) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(name, style: const TextStyle(fontSize: 14)),
      const SizedBox(height: 7),
      TextFormField(
        controller: c,
        style: const TextStyle(fontSize: 14),
        keyboardType: stock ? TextInputType.number : TextInputType.datetime,
        inputFormatters: stock
            ? [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(6),
              ]
            : null,
        decoration: InputDecoration(
          hintText: stock ? '예: 005930' : 'YYYY-MM-DD',
          hintStyle: const TextStyle(fontSize: 13, color: siteMuted),
          suffixIconConstraints: const BoxConstraints(
            minWidth: 32,
            minHeight: 40,
          ),
          suffixIcon: stock
              ? null
              : IconButton(
                  tooltip: '$name 선택',
                  icon: const Icon(Icons.calendar_today_outlined, size: 17),
                  onPressed: () async {
                    final d = await showDatePicker(
                      context: context,
                      initialDate: DateTime.tryParse(c.text) ?? DateTime.now(),
                      firstDate: DateTime(1990),
                      lastDate: DateTime.now(),
                    );
                    if (d != null) {
                      c.text = d.toIso8601String().substring(0, 10);
                    }
                  },
                ),
        ),
        validator: (v) {
          final s = v?.trim() ?? '';
          if (stock) {
            return RegExp(r'^\d{6}$').hasMatch(s) ? null : '6자리 종목코드를 입력하세요.';
          }
          if (!validDate(s)) {
            return '올바른 날짜를 입력하세요.';
          }
          if (c == exit && s.compareTo(entry.text.trim()) < 0) {
            return '청산일은 진입일 이후여야 합니다.';
          }
          return null;
        },
      ),
    ],
  );
  void review() {
    if (!form.currentState!.validate()) {
      return;
    }
    if (record == 'sample' &&
        sample != null &&
        code.text.trim() == sample!['trade']['code'] &&
        entry.text.trim() == sample!['trade']['entry'] &&
        exit.text.trim() == sample!['trade']['exit']) {
      setState(() {
        sampleVisible = true;
        showEmpty = false;
      });
      return;
    }
    setState(() {
      sampleVisible = false;
      showEmpty = false;
    });
    final chosen = widget.trades.where((t) => t.id == record).firstOrNull;
    widget.analyze(
      Trade(
        ticker: chosen?.ticker ?? code.text,
        code: code.text.trim(),
        entry: entry.text.trim(),
        exit: exit.text.trim(),
        buy: 1,
        sell: 1,
      ),
    );
  }

  Widget controls(bool mobile) {
    final current = record == 'sample'
        ? 'sample'
        : widget.trades.any((t) => t.id == record)
        ? record
        : null;
    return box(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: title('거래 선택')),
              note(sampleVisible ? '샘플' : '${widget.trades.length}건'),
            ],
          ),
          const SizedBox(height: 20),
          const Text('기존 거래 기록', style: TextStyle(fontSize: 14)),
          const SizedBox(height: 7),
          DropdownButtonFormField<String>(
            key: ValueKey(current),
            initialValue: current,
            isExpanded: true,
            hint: const Text('직접 입력하기', style: TextStyle(fontSize: 13)),
            items: [
              const DropdownMenuItem(value: null, child: Text('직접 입력하기')),
              if (sample != null)
                const DropdownMenuItem(
                  value: 'sample',
                  child: Text(
                    '에이피알 · 2026-08-06 ~ 2026-09-03',
                    style: TextStyle(fontSize: 13),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              for (final t in widget.trades)
                DropdownMenuItem(
                  value: t.id,
                  child: Text(
                    '${t.ticker} · ${t.entry} ~ ${t.exit}',
                    style: const TextStyle(fontSize: 13),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: (id) {
              if (id == 'sample') {
                selectSample();
                return;
              }
              setState(() {
                record = id;
                sampleVisible = false;
                showEmpty = id == null;
              });
              if (id == null) {
                return;
              }
              final t = widget.trades.firstWhere((t) => t.id == id);
              code.text = t.code;
              entry.text = t.entry;
              exit.text = t.exit;
              if (t.code.isNotEmpty && t.entry.isNotEmpty) {
                widget.analyze(t);
              }
            },
          ),
          const SizedBox(height: 10),
          note(
            sampleVisible
                ? '읽기 전용 샘플 · 실제 거래로 저장되지 않습니다.'
                : widget.trades.isEmpty
                ? '저장된 거래가 없습니다. 날짜를 직접 입력해 복기해 보세요.'
                : '본인 거래 기록을 연결했습니다.',
          ),
          const Divider(height: 42, color: siteLine),
          Form(
            key: form,
            child: Column(
              children: [
                input('종목코드', code, stock: true),
                const SizedBox(height: 18),
                if (mobile)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: input('진입일', entry)),
                      const SizedBox(width: 12),
                      Expanded(child: input('청산일', exit)),
                    ],
                  )
                else ...[
                  input('진입일', entry),
                  const SizedBox(height: 14),
                  input('청산일', exit),
                ],
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: widget.analyzing
                        ? null
                        : widget.connected
                        ? review
                        : widget.settings,
                    child: Text(
                      !widget.connected
                          ? '서버 연결하기'
                          : widget.analyzing
                          ? '시세 연결 중…'
                          : '차트 복기하기',
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          note(
            widget.analyzing
                ? '일별 가격을 불러오고 있습니다…'
                : !sampleVisible && widget.report == null
                ? '거래를 선택하거나 날짜를 직접 입력하세요.'
                : '분석 완료 · 입력한 날짜 기준으로 표시합니다.',
          ),
          if (widget.error != null)
            Text(
              widget.error!,
              style: const TextStyle(color: Colors.redAccent),
            ),
          const SizedBox(height: 34),
          Container(
            padding: const EdgeInsets.only(left: 14),
            decoration: const BoxDecoration(
              border: Border(left: BorderSide(color: siteMint, width: 2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                eyebrow('01 — 분석 기준'),
                note('실제 체결가 대신 해당 날짜의 종가를 기준으로 가격 변화를 계산합니다.'),
              ],
            ),
          ),
          const SizedBox(height: 28),
          TextButton(
            onPressed: widget.openMaster,
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: const Size(0, 24),
              foregroundColor: siteMuted,
            ),
            child: const Text(
              'TradingMaster 열기 ↗',
              style: TextStyle(fontSize: 13),
            ),
          ),
        ],
      ),
      padding: mobile
          ? 20
          : MediaQuery.sizeOf(context).width <= 1100
          ? 18
          : 23,
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: LayoutBuilder(
      builder: (context, c) {
        final mobile = c.maxWidth <= 760,
            padding = mobile ? 18.0 : c.maxWidth * .045;
        final report = SitesReport(
          trade: sampleVisible
              ? Trade.fromJson({...sample!['trade'], 'id': ''})
              : widget.selected,
          report: showEmpty
              ? null
              : sampleVisible
              ? Map<String, dynamic>.from(sample!['report'])
              : widget.report,
          loading: !sampleVisible && widget.analyzing,
          error: sampleVisible || showEmpty ? null : widget.reviewError,
        );
        return SingleChildScrollView(
          controller: pageScroll,
          child: Column(
            children: [
              Container(
                height: mobile ? 68 : 83,
                padding: EdgeInsets.symmetric(horizontal: padding),
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: siteLine)),
                ),
                child: Row(
                  children: [
                    const Text(
                      '⌁',
                      style: TextStyle(color: siteMint, fontSize: 36),
                    ),
                    const SizedBox(width: 12),
                    const SizedBox(
                      width: 110,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Text.rich(
                          TextSpan(
                            children: [
                              TextSpan(text: 'Trend'),
                              TextSpan(
                                text: 'Lab',
                                style: TextStyle(color: siteMint),
                              ),
                            ],
                          ),
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                    if (!mobile) ...[
                      const SizedBox(width: 32),
                      note('나의 추세추종 복기', size: 14),
                    ],
                    const Spacer(),
                    pill('PILOT 01'),
                    PopupMenuButton<String>(
                      tooltip: '기록 관리 및 샘플',
                      onSelected: (action) {
                        final selected = widget.trades
                            .where((t) => t.id == record)
                            .firstOrNull;
                        switch (action) {
                          case 'sample':
                            selectSample();
                          case 'new':
                            widget.edit(null);
                          case 'import':
                            widget.importRecords();
                          case 'refresh':
                            widget.refresh();
                          case 'edit':
                            if (selected != null) {
                              widget.edit(selected);
                            }
                          case 'delete':
                            if (selected != null) {
                              widget.remove(selected);
                            }
                        }
                      },
                      itemBuilder: (_) => [
                        const PopupMenuItem(
                          value: 'sample',
                          child: Text('샘플 보기'),
                        ),
                        const PopupMenuItem(value: 'new', child: Text('거래 기록')),
                        const PopupMenuItem(
                          value: 'import',
                          child: Text('기존 기록 가져오기'),
                        ),
                        const PopupMenuItem(
                          value: 'refresh',
                          child: Text('거래 목록 새로고침'),
                        ),
                        if (widget.trades.any((t) => t.id == record)) ...[
                          const PopupMenuItem(
                            value: 'edit',
                            child: Text('거래 수정'),
                          ),
                          const PopupMenuItem(
                            value: 'delete',
                            child: Text('거래 삭제'),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1510),
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                      padding,
                      mobile ? 26 : 40,
                      padding,
                      0,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  eyebrow('TRADE REVIEW / 날짜로 돌아보는 거래'),
                                  title(
                                    '그때의 추세를, 다시 보다.',
                                    size: mobile ? 26 : 31,
                                  ),
                                  const SizedBox(height: 10),
                                  note(
                                    '종목과 두 날짜로 진입부터 청산까지의 가격 흐름을 살펴보세요.',
                                    size: 15,
                                  ),
                                ],
                              ),
                            ),
                            if (!mobile) note('국내 주식 · 일봉'),
                          ],
                        ),
                        const SizedBox(height: 30),
                        if (mobile) ...[
                          controls(true),
                          const SizedBox(height: 24),
                          report,
                        ] else
                          StickyReviewPair(
                            scroll: pageScroll,
                            width: c.maxWidth <= 1100 ? 245 : 280,
                            gap: c.maxWidth <= 1100 ? 18 : 26,
                            controls: controls(false),
                            report: report,
                          ),
                        const SizedBox(height: 40),
                        const Divider(color: siteLine),
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 22),
                          child: mobile
                              ? Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    note(
                                      'Trend Lab / TradingMaster의 독립 시범 앱',
                                      size: 12,
                                    ),
                                    note('기록을 복기하는 도구입니다.', size: 12),
                                  ],
                                )
                              : Row(
                                  children: [
                                    Expanded(
                                      child: note(
                                        'Trend Lab / TradingMaster의 독립 시범 앱',
                                        size: 12,
                                      ),
                                    ),
                                    note('기록을 복기하는 도구입니다.', size: 12),
                                  ],
                                ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    ),
  );
}

class StickyReviewPair extends StatefulWidget {
  final ScrollController scroll;
  final double width, gap;
  final Widget controls, report;
  const StickyReviewPair({
    super.key,
    required this.scroll,
    required this.width,
    required this.gap,
    required this.controls,
    required this.report,
  });
  @override
  State<StickyReviewPair> createState() => _StickyReviewPairState();
}

class _StickyReviewPairState extends State<StickyReviewPair> {
  final rowKey = GlobalKey(), controlKey = GlobalKey();
  double offset = 0;
  bool scheduled = false;
  @override
  void initState() {
    super.initState();
    widget.scroll.addListener(measure);
    measure();
  }

  @override
  void dispose() {
    widget.scroll.removeListener(measure);
    super.dispose();
  }

  void measure() {
    if (scheduled) {
      return;
    }
    scheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      scheduled = false;
      if (!mounted) {
        return;
      }
      final row = rowKey.currentContext?.findRenderObject() as RenderBox?;
      final control =
          controlKey.currentContext?.findRenderObject() as RenderBox?;
      final viewport =
          Scrollable.maybeOf(context)?.context.findRenderObject() as RenderBox?;
      if (row == null || control == null || viewport == null) {
        return;
      }
      final top = viewport.localToGlobal(Offset.zero).dy + 24;
      final next = (top - row.localToGlobal(Offset.zero).dy)
          .clamp(0.0, math.max(0.0, row.size.height - control.size.height))
          .toDouble();
      if ((next - offset).abs() > .5) {
        setState(() => offset = next);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    measure();
    return Row(
      key: rowKey,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: widget.width,
          child: Transform.translate(
            offset: Offset(0, offset),
            child: Container(key: controlKey, child: widget.controls),
          ),
        ),
        SizedBox(width: widget.gap),
        Expanded(child: widget.report),
      ],
    );
  }
}

class SitesReport extends StatelessWidget {
  final Trade? trade;
  final Map<String, dynamic>? report;
  final bool loading;
  final String? error;
  const SitesReport({
    super.key,
    this.trade,
    this.report,
    required this.loading,
    this.error,
  });
  @override
  Widget build(BuildContext context) {
    final r = report;
    if (r == null) {
      return box(
        SizedBox(
          width: double.infinity,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 80),
            child: Column(
              children: [
                const Text(
                  '⌁',
                  style: TextStyle(color: siteMint, fontSize: 50),
                ),
                title(
                  loading
                      ? '거래의 흐름을 연결하고 있어요'
                      : error != null
                      ? '시세를 연결하지 못했어요'
                      : '거래의 흐름을 살펴보세요',
                  size: 21,
                ),
                const SizedBox(height: 10),
                note(
                  error ??
                      (loading
                          ? '가격과 이동평균선을 준비합니다.'
                          : '왼쪽에서 종목코드와 진입·청산일을 입력해 주세요.'),
                ),
                if (loading)
                  const Padding(
                    padding: EdgeInsets.all(20),
                    child: LinearProgressIndicator(),
                  ),
              ],
            ),
          ),
        ),
      );
    }
    final range = r['range'] as Map?;
    final metrics = [
      (
        '종가 기준 변화',
        percent(r['closeChange'] as num),
        sign(r['closeChange'] as num),
        '실제 체결 수익률 아님',
      ),
      ('보유기간', '${r['holding']}일', Colors.white, '${r['sessions']}개 거래일 포함'),
      (
        '구간 최고가 변화',
        range == null ? '—' : percent(range['up'] as num),
        range == null ? siteMuted : sign(range['up'] as num),
        '진입·청산 당일 제외',
      ),
      (
        '구간 최저가 변화',
        range == null ? '—' : percent(range['down'] as num),
        range == null ? siteMuted : sign(range['down'] as num),
        '진입일 종가 대비',
      ),
    ];
    final conditions = box(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [eyebrow('ENTRY / 진입 당시'), title('상승 추세 조건')],
                ),
              ),
              Text(
                '${r['passed']} / ${r['known']}',
                style: const TextStyle(fontSize: 20, color: siteMint),
              ),
            ],
          ),
          const SizedBox(height: 20),
          for (final criterion in r['criteria'] as List)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Icon(
                    criterion['ok'] == null
                        ? Icons.help_outline
                        : criterion['ok']
                        ? Icons.check_circle_outline
                        : Icons.remove_circle_outline,
                    size: 20,
                    color: criterion['ok'] == true
                        ? siteMint
                        : Colors.redAccent,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      criterion['label'] as String,
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
                  const SizedBox(width: 8),
                  note(
                    criterion['ok'] == null
                        ? '미확인'
                        : criterion['ok']
                        ? '충족'
                        : '미충족',
                    size: 12,
                  ),
                ],
              ),
            ),
          foot('미너비니의 추세 템플릿 중 가격으로 확인 가능한 7개 조건입니다. RS·VCP·돌파 여부는 판정하지 않습니다.'),
        ],
      ),
    );
    final future = box(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    eyebrow('AFTER EXIT / 청산 이후'),
                    title('시간이 지난 뒤의 흐름'),
                  ],
                ),
              ),
              const Icon(Icons.schedule, color: siteMint),
            ],
          ),
          const SizedBox(height: 12),
          for (final f in r['future'] as List)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 15),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: siteLine)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${f['days']}거래일 후'),
                        note(f['date'] as String? ?? '시세 없음', size: 12),
                      ],
                    ),
                  ),
                  Text(
                    f['change'] == null ? '—' : percent(f['change'] as num),
                    style: TextStyle(
                      fontSize: 24,
                      color: f['change'] == null
                          ? siteMuted
                          : sign(f['change'] as num),
                    ),
                  ),
                ],
              ),
            ),
          foot('청산일 종가 대비 변화입니다. 이후 상승이 있었다는 이유만으로 당시 청산이 잘못됐다고 판단하지 않습니다.'),
        ],
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  eyebrow('${trade?.code ?? ''} / TRADE REVIEW'),
                  title(r['name'] as String? ?? trade?.ticker ?? '', size: 25),
                  const SizedBox(height: 4),
                  note(
                    '${trade?.entry ?? ''} — ${trade?.exit ?? ''}',
                    size: 14,
                  ),
                ],
              ),
            ),
            pill('시세 연결 완료'),
          ],
        ),
        const SizedBox(height: 22),
        LayoutBuilder(
          builder: (_, c) {
            final n = c.maxWidth < 850 ? 2 : 4;
            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (final m in metrics)
                  SizedBox(
                    width: (c.maxWidth - 12 * (n - 1)) / n,
                    child: box(
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          note(m.$1),
                          const SizedBox(height: 8),
                          Text(
                            m.$2,
                            style: TextStyle(
                              fontSize: 25,
                              color: m.$3,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 4),
                          note(m.$4, size: 12),
                        ],
                      ),
                      padding: 17,
                    ),
                  ),
              ],
            );
          },
        ),
        const SizedBox(height: 20),
        SitesChart(report: r),
        const SizedBox(height: 20),
        LayoutBuilder(
          builder: (_, c) => c.maxWidth < 850
              ? Column(
                  children: [conditions, const SizedBox(height: 20), future],
                )
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 11, child: conditions),
                    const SizedBox(width: 20),
                    Expanded(flex: 10, child: future),
                  ],
                ),
        ),
        const SizedBox(height: 20),
        box(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        eyebrow('REVIEW NOTES'),
                        title('이번 거래의 복기 질문'),
                      ],
                    ),
                  ),
                  pill('가격 데이터 기반'),
                ],
              ),
              const SizedBox(height: 20),
              LayoutBuilder(
                builder: (_, c) => Wrap(
                  spacing: 25,
                  runSpacing: 20,
                  children: [
                    for (final n in r['observations'] as List)
                      SizedBox(
                        width: c.maxWidth < 700
                            ? c.maxWidth
                            : (c.maxWidth - 25) / 2,
                        child: Container(
                          padding: const EdgeInsets.only(left: 16),
                          decoration: const BoxDecoration(
                            border: Border(
                              left: BorderSide(
                                color: Color(0xff477162),
                                width: 2,
                              ),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              title(n['title'] as String, size: 15),
                              const SizedBox(height: 10),
                              note(n['text'] as String, size: 14),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        box(
          ExpansionTile(
            title: const Text(
              '이 분석으로 알 수 있는 것과 없는 것',
              style: TextStyle(fontSize: 14),
            ),
            childrenPadding: const EdgeInsets.fromLTRB(19, 0, 19, 19),
            children: [
              for (final text in [
                '진입·청산일과 일봉으로 당시 가격 추세를 확인합니다. 실제 체결 수익률, 수수료, 분할매매, 거래 중 실제 최대 수익·손실(MFE·MAE)은 계산하지 않습니다.',
                '구간 최고·최저가 변화는 진입일 종가 대비 중간 거래일의 고가·저가입니다. 진입·청산 당일은 제외합니다. 일봉으로는 장중 가격의 이동 순서를 알 수 없습니다.',
                '거래일이 아닌 진입일은 다음 거래일, 청산일은 이전 거래일에 맞춰 표시합니다. 날짜가 조정되면 차트 아래에 안내합니다.',
                '이동평균선과 추세 조건은 해당 날짜까지의 시세로 계산합니다. 청산 후 결과는 복기용이며 진입 당시의 판단에 사용하지 않습니다. 시세 공급자의 과거 가격 조정 방식에 따라 실제 당시 표시 가격과 차이가 있을 수 있습니다.',
                '한 거래의 결과로 적합한 전략을 확정하지 않습니다.',
              ])
                Padding(
                  padding: const EdgeInsets.only(top: 13),
                  child: note(text, size: 14),
                ),
            ],
          ),
          padding: 4,
        ),
      ],
    );
  }
}

class SitesChart extends StatefulWidget {
  final Map<String, dynamic> report;
  const SitesChart({super.key, required this.report});
  @override
  State<SitesChart> createState() => _SitesChartState();
}

class _SitesChartState extends State<SitesChart> {
  int window = 40;
  final averages = <int>{20, 50};
  int? hovered;
  final chartFocus = FocusNode();
  @override
  void dispose() {
    chartFocus.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(SitesChart old) {
    super.didUpdateWidget(old);
    if (old.report != widget.report) {
      hovered = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.report, bars = r['bars'] as List;
    final start = math.max(0, (r['entryIndex'] as int) - window),
        end = math.min(bars.length - 1, (r['exitIndex'] as int) + window);
    final b = hovered == null ? null : bars[hovered!];
    return box(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 20,
            runSpacing: 12,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  title('진입에서 청산까지'),
                  const SizedBox(height: 5),
                  note('${r['entry']['date']} 진입 · ${r['exit']['date']} 청산'),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  color: const Color(0xff0c1726),
                  borderRadius: BorderRadius.circular(7),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final n in [40, 120])
                      TextButton(
                        onPressed: () => setState(() {
                          window = n;
                          hovered = null;
                        }),
                        style: TextButton.styleFrom(
                          backgroundColor: window == n
                              ? const Color(0xff203d3a)
                              : Colors.transparent,
                          foregroundColor: window == n ? siteMint : siteMuted,
                          minimumSize: Size.zero,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 7,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                        child: Text(
                          '앞뒤 $n일',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Text(
                '━ 종가',
                style: TextStyle(fontSize: 12, color: siteMint),
              ),
              for (final n in averagesColors.keys)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 24,
                      height: 28,
                      child: Checkbox(
                        key: ValueKey('ma$n'),
                        value: averages.contains(n),
                        onChanged: (_) => setState(() {
                          averages.contains(n)
                              ? averages.remove(n)
                              : averages.add(n);
                        }),
                        activeColor: siteMint,
                      ),
                    ),
                    Text(
                      '━ $n일',
                      style: TextStyle(fontSize: 12, color: averagesColors[n]),
                    ),
                  ],
                ),
              note('▰ 보유 구간', size: 12),
            ],
          ),
          const SizedBox(height: 10),
          LayoutBuilder(
            builder: (_, c) {
              void point(Offset p) => setState(
                () => hovered =
                    (start +
                            ((p.dx / c.maxWidth * 960 - 15) /
                                    869 *
                                    (end - start))
                                .round())
                        .clamp(start, end),
              );
              return CallbackShortcuts(
                bindings: {
                  const SingleActivator(LogicalKeyboardKey.arrowLeft): () =>
                      setState(
                        () => hovered = ((hovered ?? start) - 1).clamp(
                          start,
                          end,
                        ),
                      ),
                  const SingleActivator(LogicalKeyboardKey.arrowRight): () =>
                      setState(
                        () => hovered = ((hovered ?? start) + 1).clamp(
                          start,
                          end,
                        ),
                      ),
                },
                child: Focus(
                  focusNode: chartFocus,
                  child: Semantics(
                    label: '차트 날짜 선택, 좌우 화살표로 이동',
                    slider: true,
                    value: b == null
                        ? '날짜를 선택하세요'
                        : '${b['date']} 종가 ${money(b['close'] as num)}',
                    child: MouseRegion(
                      onHover: (e) => point(e.localPosition),
                      onExit: (_) => setState(() => hovered = null),
                      child: GestureDetector(
                        onTapDown: (e) {
                          chartFocus.requestFocus();
                          point(e.localPosition);
                        },
                        onHorizontalDragUpdate: (e) => point(e.localPosition),
                        child: SizedBox(
                          width: double.infinity,
                          height: math.max(
                            255.0,
                            math.min(430.0, c.maxWidth * 430 / 960),
                          ),
                          child: CustomPaint(
                            key: const ValueKey('sites-price-chart'),
                            painter: SitesPricePainter(
                              r,
                              window: window,
                              averages: Set.of(averages),
                              hovered: hovered,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 10),
          note(
            b == null
                ? '차트 위에서 날짜별 가격을 확인하세요.'
                : '${b['date']} · 종가 ${money(b['close'] as num)} · 고가 ${money(b['high'] as num? ?? b['close'] as num)} · 저가 ${money(b['low'] as num? ?? b['close'] as num)} · 거래량 ${money(b['volume'] as num).replaceAll('원', '')}주',
            size: 12,
          ),
          if (r['aligned'] == true)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                '비거래일 조정: 진입 ${r['entry']['date']} · 청산 ${r['exit']['date']}',
                style: const TextStyle(color: Color(0xfff0c675), fontSize: 12),
              ),
            ),
          const Divider(height: 30, color: siteLine),
          Wrap(
            spacing: 24,
            runSpacing: 5,
            children: [
              note('${r['source']} · 최신 시세 ${bars.last['date']}', size: 12),
              note('종가는 원 단위 · 거래량은 주 단위', size: 12),
            ],
          ),
        ],
      ),
    );
  }
}
