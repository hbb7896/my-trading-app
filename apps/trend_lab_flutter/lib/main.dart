import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'trade.dart';
import 'import_dialog.dart';
import 'auth_gate.dart';

const mint = Color(0xff75e3bf),
    background = Color(0xff0b1220),
    panel = Color(0xff142033);
void main() => runApp(const TrendLabApp());
String money(num n) =>
    '${n.round().toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}원';
String percent(num n) => '${n >= 0 ? '+' : ''}${n.toStringAsFixed(2)}%';
Color sign(num n) => n >= 0 ? mint : const Color(0xffff8d9d);

class TrendLabApp extends StatelessWidget {
  const TrendLabApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Trend Lab',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: ColorScheme.fromSeed(
        seedColor: mint,
        brightness: Brightness.dark,
        surface: panel,
      ),
      useMaterial3: true,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
      ),
      cardTheme: const CardThemeData(color: panel, elevation: 0),
    ),
    home: AuthGate(
      child: (api) => JournalScreen(
        key: ValueKey(api?.baseUrl ?? 'local'),
        initialApi: api,
      ),
    ),
  );
}

class JournalScreen extends StatefulWidget {
  final TradingApi? initialApi;
  const JournalScreen({super.key, this.initialApi});
  @override
  State<JournalScreen> createState() => _JournalScreenState();
}

class _JournalScreenState extends State<JournalScreen>
    with WidgetsBindingObserver {
  TradingApi? api;
  List<Trade> trades = [];
  Trade? selected;
  Map<String, dynamic>? report;
  bool loading = false, analyzing = false;
  String? error, reviewError;
  String query = '';
  DateTime? synced;
  int reviewSequence = 0;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    api = widget.initialApi;
    if (api != null) Future.microtask(refresh);
    timer = Timer.periodic(const Duration(seconds: 30), (_) => refresh());
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  Future<void> refresh() async {
    final client = api;
    if (client == null || loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final data = await client.trades();
      if (!mounted || api != client) return;
      Trade? replacement;
      for (final t in data) {
        if (t.id == selected?.id) replacement = t;
      }
      final changed =
          selected != null &&
          (replacement == null ||
              replacement.code != selected!.code ||
              replacement.entry != selected!.entry ||
              replacement.exit != selected!.exit);
      setState(() {
        trades = data;
        synced = DateTime.now();
        selected = replacement;
        if (changed) {
          reviewSequence++;
          report = null;
          analyzing = false;
        }
      });
      if (changed && replacement != null) analyze(replacement);
    } catch (e) {
      if (mounted && api == client) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> settings() async {
    if (widget.initialApi != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('본인 로그인으로 온라인 저장소에 연결되어 있습니다.')),
      );
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final url = TextEditingController(
          text:
              api?.baseUrl ??
              prefs.getString('api_url') ??
              (kIsWeb
                  ? Uri.base.origin
                  : const String.fromEnvironment(
                      'API_BASE_URL',
                      defaultValue: 'http://10.0.2.2:8787',
                    )),
        ),
        key = TextEditingController(text: api?.token ?? '');
    final form = GlobalKey<FormState>();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('공통 서버 연결'),
        content: SizedBox(
          width: 420,
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '웹과 휴대폰에서 같은 서버 주소와 연결 키를 사용하세요. 키는 이번 실행 동안만 유지됩니다.',
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: url,
                  decoration: const InputDecoration(labelText: 'API 서버 주소'),
                  validator: (v) {
                    final u = Uri.tryParse(v?.trim() ?? '');
                    return u != null &&
                            ['http', 'https'].contains(u.scheme) &&
                            u.host.isNotEmpty &&
                            u.userInfo.isEmpty &&
                            u.query.isEmpty &&
                            u.fragment.isEmpty
                        ? null
                        : 'http 또는 https 서버 주소를 입력하세요.';
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: key,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: '개인 연결 키'),
                  validator: (v) =>
                      (v?.length ?? 0) < 24 ? '24자 이상의 연결 키를 입력하세요.' : null,
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () {
              if (form.currentState!.validate()) Navigator.pop(c, true);
            },
            child: const Text('연결'),
          ),
        ],
      ),
    );
    if (accepted == true && mounted) {
      final base = url.text.trim().replaceAll(RegExp(r'/+$'), '');
      await prefs.setString('api_url', base);
      if (!mounted) return;
      setState(() {
        api = TradingApi(base, key.text);
        trades = [];
        selected = null;
        report = null;
        synced = null;
        reviewSequence++;
      });
      await refresh();
    }
    url.dispose();
    key.dispose();
  }

  void notify(Object e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  Future<void> importRecords() async {
    final client = api;
    if (client == null) {
      await settings();
      return;
    }
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ImportDialog(api: client),
    );
    if (result != null) {
      await refresh();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(result)));
      }
    }
  }

  Future<void> edit([Trade? t]) async {
    final client = api;
    if (client == null) {
      await settings();
      return;
    }
    final saved = await showDialog<Trade>(
      context: context,
      builder: (_) => TradeEditor(trade: t),
    );
    if (saved == null) return;
    try {
      await client.save(saved);
      await refresh();
    } catch (e) {
      notify(e);
    }
  }

  Future<void> remove(Trade t) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('거래 삭제'),
        content: Text('${t.ticker}의 거래를 영구 삭제할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (yes != true) return;
    try {
      await api!.delete(t);
      await refresh();
    } catch (e) {
      notify(e);
    }
  }

  Future<void> analyze(Trade t) async {
    if (t.code.isEmpty || t.entry.isEmpty) {
      setState(() {
        selected = t;
        report = null;
        analyzing = false;
        reviewSequence++;
        reviewError = '차트 복기에 필요한 종목코드와 진입일을 거래 수정에서 입력하세요.';
      });
      return;
    }
    final seq = ++reviewSequence;
    setState(() {
      selected = t;
      report = null;
      reviewError = null;
      analyzing = true;
    });
    try {
      final data = await api!.review(t);
      if (mounted && seq == reviewSequence) setState(() => report = data);
    } catch (e) {
      if (mounted && seq == reviewSequence) {
        setState(
          () => reviewError = e.toString().replaceFirst('Exception: ', ''),
        );
      }
    } finally {
      if (mounted && seq == reviewSequence) setState(() => analyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final visible = trades
            .where(
              (t) => '${t.ticker} ${t.code} ${t.memo}'.toLowerCase().contains(
                query.toLowerCase(),
              ),
            )
            .toList(),
        net = trades.fold<double>(0, (s, t) => s + t.pnl),
        wins = trades.where((t) => t.pnl > 0).length;
    final wide = MediaQuery.sizeOf(context).width >= 1000;
    final journal = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: Text(
                '거래 기록',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
            ),
            Text('${visible.length}건', style: const TextStyle(color: mint)),
          ],
        ),
        const SizedBox(height: 16),
        TextField(
          onChanged: (v) => setState(() => query = v),
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: '종목명 · 코드 · 메모 검색',
          ),
        ),
        const SizedBox(height: 16),
        if (visible.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 36),
            child: Text(
              api == null
                  ? '공통 서버를 연결하면 거래기록이 표시됩니다.'
                  : '거래가 없습니다. 첫 거래를 기록해보세요.',
            ),
          ),
        ...visible.map(
          (t) => Card(
            child: InkWell(
              onTap: () => analyze(t),
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            t.ticker,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Text(
                          percent(t.roi),
                          style: TextStyle(
                            color: sign(t.pnl),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        PopupMenuButton<String>(
                          onSelected: (v) => v == 'edit' ? edit(t) : remove(t),
                          itemBuilder: (_) => [
                            const PopupMenuItem(
                              value: 'edit',
                              child: Text('거래 수정'),
                            ),
                            const PopupMenuItem(
                              value: 'delete',
                              child: Text('거래 삭제'),
                            ),
                          ],
                        ),
                      ],
                    ),
                    Text(
                      '${t.entry} → ${t.exit}',
                      style: const TextStyle(color: Colors.white60),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          t.code,
                          style: const TextStyle(color: Colors.white38),
                        ),
                        const Spacer(),
                        Text(
                          money(t.pnl),
                          style: TextStyle(color: sign(t.pnl)),
                        ),
                      ],
                    ),
                    if (t.memo.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                          t.memo,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
    final review = ReviewPanel(
      trade: selected,
      report: report,
      loading: analyzing,
      error: reviewError,
    );
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '⌁  Trend Lab',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        actions: [
          IconButton(
            tooltip: '기존 기록 가져오기',
            onPressed: loading ? null : importRecords,
            icon: const Icon(Icons.upload_file),
          ),
          IconButton(
            tooltip: '거래 새로고침',
            onPressed: loading ? null : refresh,
            icon: const Icon(Icons.sync),
          ),
          IconButton(
            tooltip: '서버 연결',
            onPressed: loading ? null : settings,
            icon: const Icon(Icons.settings_outlined),
          ),
          const SizedBox(width: 12),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => edit(),
        icon: const Icon(Icons.add),
        label: const Text('거래 기록'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1400),
          child: ListView(
            padding: EdgeInsets.all(wide ? 32 : 20),
            children: [
              const Text(
                'RECORD · REFLECT · REPEAT',
                style: TextStyle(color: mint, letterSpacing: 2, fontSize: 12),
              ),
              const SizedBox(height: 12),
              const Text(
                '나의 거래를, 더 선명하게.',
                style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                api == null
                    ? '웹과 안드로이드에서 이어지는 나의 매매일지'
                    : '공통 서버 연결됨${synced == null ? '' : ' · ${synced!.hour}:${synced!.minute.toString().padLeft(2, '0')} 갱신'}',
                style: const TextStyle(color: Colors.white60),
              ),
              if (api == null)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: FilledButton.icon(
                      onPressed: settings,
                      icon: const Icon(Icons.link),
                      label: const Text('서버 연결하기'),
                    ),
                  ),
                ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(
                    error!,
                    style: const TextStyle(color: Colors.orangeAccent),
                  ),
                ),
              if (loading) const LinearProgressIndicator(),
              const SizedBox(height: 24),
              Wrap(
                spacing: 14,
                runSpacing: 14,
                children: [
                  Metric('총 손익', money(net), sign(net)),
                  Metric('거래 수', '${trades.length}건', Colors.white),
                  Metric(
                    '승률',
                    trades.isEmpty
                        ? '—'
                        : '${(wins / trades.length * 100).toStringAsFixed(1)}%',
                    mint,
                  ),
                ],
              ),
              const SizedBox(height: 32),
              if (wide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 4, child: journal),
                    const SizedBox(width: 24),
                    Expanded(flex: 6, child: review),
                  ],
                )
              else ...[
                journal,
                const SizedBox(height: 24),
                review,
              ],
              const SizedBox(height: 90),
            ],
          ),
        ),
      ),
    );
  }
}

class Metric extends StatelessWidget {
  final String label, value;
  final Color color;
  const Metric(this.label, this.value, this.color, {super.key});
  @override
  Widget build(BuildContext context) => SizedBox(
    width: 220,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: Colors.white60)),
            const SizedBox(height: 10),
            Text(
              value,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class TradeEditor extends StatefulWidget {
  final Trade? trade;
  const TradeEditor({super.key, this.trade});
  @override
  State<TradeEditor> createState() => _TradeEditorState();
}

class _TradeEditorState extends State<TradeEditor> {
  final form = GlobalKey<FormState>();
  late List<TextEditingController> c;
  @override
  void initState() {
    super.initState();
    final t = widget.trade;
    c = [
      t?.ticker ?? '',
      t?.code ?? '',
      t?.entry ?? '',
      t?.exit ?? '',
      t?.buy.toString() ?? '',
      t?.sell.toString() ?? '',
      t?.memo ?? '',
    ].map((v) => TextEditingController(text: v)).toList();
  }

  @override
  void dispose() {
    for (final x in c) {
      x.dispose();
    }
    super.dispose();
  }

  bool date(String v) {
    final d = DateTime.tryParse(v);
    return RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(v) &&
        d != null &&
        d.toIso8601String().substring(0, 10) == v;
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.trade == null ? '새 거래 기록' : '거래 수정'),
    content: SizedBox(
      width: 480,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (int i = 0; i < c.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: TextFormField(
                    controller: c[i],
                    maxLines: i == 6 ? 3 : 1,
                    maxLength: i == 6 ? 10000 : null,
                    keyboardType: i == 1
                        ? TextInputType.number
                        : i == 4 || i == 5
                        ? const TextInputType.numberWithOptions(decimal: true)
                        : TextInputType.text,
                    decoration: InputDecoration(
                      labelText: [
                        '종목명',
                        '6자리 종목코드 (차트 복기 시 필요)',
                        '진입일 (선택 · YYYY-MM-DD)',
                        '청산일 (YYYY-MM-DD)',
                        '총 매수금액 (원)',
                        '총 매도금액 (원)',
                        '복기 메모',
                      ][i],
                    ),
                    validator: (v) {
                      final s = v?.trim() ?? '';
                      if (i == 0 && (s.isEmpty || s.length > 100)) {
                        return '종목명을 입력하세요.';
                      }
                      if (i == 1 &&
                          s.isNotEmpty &&
                          !RegExp(r'^\d{6}$').hasMatch(s)) {
                        return '6자리 종목코드를 입력하세요.';
                      }
                      if ((i == 2 && s.isNotEmpty || i == 3) && !date(s)) {
                        return '올바른 날짜를 입력하세요.';
                      }
                      if (i == 3 && s.compareTo(c[2].text.trim()) < 0) {
                        return '청산일은 진입일 이후여야 합니다.';
                      }
                      if (i == 4 || i == 5) {
                        final n = double.tryParse(s);
                        if (n == null ||
                            !n.isFinite ||
                            n < 0 ||
                            n > 1e15 ||
                            (i == 4 && n == 0)) {
                          return '올바른 금액을 입력하세요.';
                        }
                      }
                      return null;
                    },
                  ),
                ),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('취소'),
      ),
      FilledButton(
        onPressed: () {
          if (form.currentState!.validate()) {
            Navigator.pop(
              context,
              Trade(
                id: widget.trade?.id ?? '',
                ticker: c[0].text.trim(),
                code: c[1].text.trim(),
                entry: c[2].text.trim(),
                exit: c[3].text.trim(),
                buy: double.parse(c[4].text),
                sell: double.parse(c[5].text),
                memo: c[6].text,
                extra: widget.trade?.extra ?? const {},
              ),
            );
          }
        },
        child: const Text('저장'),
      ),
    ],
  );
}

class ReviewPanel extends StatelessWidget {
  final Trade? trade;
  final Map<String, dynamic>? report;
  final bool loading;
  final String? error;
  const ReviewPanel({
    super.key,
    this.trade,
    this.report,
    this.loading = false,
    this.error,
  });
  @override
  Widget build(BuildContext context) {
    final r = report;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'CHART REVIEW',
              style: TextStyle(color: mint, letterSpacing: 2, fontSize: 12),
            ),
            const SizedBox(height: 12),
            Text(
              trade?.ticker ?? '그때의 추세를, 다시 보다.',
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              trade == null
                  ? '거래를 선택하면 진입부터 청산까지의 차트와 추세 조건을 확인합니다.'
                  : '${trade!.entry} → ${trade!.exit}',
              style: const TextStyle(color: Colors.white60),
            ),
            if (loading) ...[
              const SizedBox(height: 30),
              const LinearProgressIndicator(),
              const SizedBox(height: 16),
              const Text('일별 시세를 연결하고 있습니다…'),
            ],
            if (error != null)
              Padding(
                padding: const EdgeInsets.only(top: 24),
                child: Text(
                  error!,
                  style: const TextStyle(color: Colors.orangeAccent),
                ),
              ),
            if (r != null) ...[
              const SizedBox(height: 24),
              Text(
                '종가 기준 ${percent(r['closeChange'] as num)} · ${r['holding']}일 보유',
                style: const TextStyle(fontSize: 18),
              ),
              const SizedBox(height: 8),
              const Text(
                '실제 체결 수익률과 다릅니다. 선: 종가 / 노랑: 50일선 / 세로선: 진입·청산',
                style: TextStyle(color: Colors.white54, fontSize: 12),
              ),
              const SizedBox(height: 20),
              SizedBox(
                height: 260,
                width: double.infinity,
                child: CustomPaint(painter: PricePainter(r)),
              ),
              const SizedBox(height: 20),
              Text(
                '진입일 추세 조건 ${r['passed']} / ${r['known']}',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              for (final criterion in r['criteria'] as List)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Icon(
                        criterion['ok'] == null
                            ? Icons.help_outline
                            : criterion['ok']
                            ? Icons.check_circle_outline
                            : Icons.remove_circle_outline,
                        color: criterion['ok'] == true ? mint : Colors.white38,
                        size: 20,
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: Text(criterion['label'] as String)),
                      Text(
                        criterion['ok'] == null
                            ? '미확인'
                            : criterion['ok']
                            ? '충족'
                            : '미충족',
                        style: const TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              const Divider(height: 32),
              const Text(
                '청산 이후',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              for (final f in r['future'] as List)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${f['days']}거래일 후'),
                  subtitle: Text(f['date'] as String? ?? '시세 없음'),
                  trailing: Text(
                    f['change'] == null ? '—' : percent(f['change'] as num),
                  ),
                ),
              const Divider(),
              for (final note in r['observations'] as List) ...[
                Text(
                  note['title'] as String,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  note['text'] as String,
                  style: const TextStyle(color: Colors.white60),
                ),
                const SizedBox(height: 20),
              ],
              Text(
                '${r['source']} · 일봉 기준. 비거래일은 진입 다음 거래일·청산 이전 거래일로 조정합니다.',
                style: const TextStyle(fontSize: 12, color: Colors.white38),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class PricePainter extends CustomPainter {
  final Map<String, dynamic> report;
  PricePainter(this.report);
  @override
  void paint(Canvas canvas, Size size) {
    final all = report['bars'] as List,
        e = report['entryIndex'] as int,
        z = report['exitIndex'] as int,
        start = math.max(0, e - 40),
        end = math.min(all.length - 1, z + 40),
        bars = all.sublist(start, end + 1);
    final values = <double>[];
    for (final b in bars) {
      values.add((b['close'] as num).toDouble());
      if (b['ma50'] != null) values.add((b['ma50'] as num).toDouble());
    }
    if (values.isEmpty) return;
    final lo = values.reduce(math.min),
        hi = values.reduce(math.max),
        range = math.max(hi - lo, 1),
        right = size.width - 65,
        top = 15.0,
        bottom = size.height - 30;
    double x(int i) => i / math.max(bars.length - 1, 1) * right;
    double y(num v) =>
        bottom - ((v - lo) / range * .85 + .075) * (bottom - top);
    for (int i = 0; i < 4; i++) {
      final yy = top + i / 3 * (bottom - top);
      canvas.drawLine(
        Offset(0, yy),
        Offset(right, yy),
        Paint()..color = Colors.white12,
      );
      final text = TextPainter(
        text: TextSpan(
          text: ((hi - lo) * (1 - i / 3) + lo).round().toString(),
          style: const TextStyle(color: Colors.white54, fontSize: 10),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      text.paint(canvas, Offset(right + 8, yy - 6));
    }
    for (final key in ['close', 'ma50']) {
      final path = Path();
      bool begun = false;
      for (int i = 0; i < bars.length; i++) {
        final v = bars[i][key] as num?;
        if (v == null) {
          begun = false;
          continue;
        }
        if (!begun) {
          path.moveTo(x(i), y(v));
          begun = true;
        } else {
          path.lineTo(x(i), y(v));
        }
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = (key == 'close' ? mint : const Color(0xfff0c974))
          ..style = PaintingStyle.stroke
          ..strokeWidth = (key == 'close' ? 2 : 1.4),
      );
    }
    for (final index in [e, z]) {
      canvas.drawLine(
        Offset(x(index - start), top),
        Offset(x(index - start), bottom),
        Paint()..color = const Color(0xff70a9fa),
      );
    }
    for (final i in [0, bars.length - 1]) {
      final text = TextPainter(
        text: TextSpan(
          text: bars[i]['date'] as String,
          style: const TextStyle(color: Colors.white54, fontSize: 11),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      text.paint(
        canvas,
        Offset(i == 0 ? 0 : math.max(0, right - text.width), size.height - 18),
      );
    }
  }

  @override
  bool shouldRepaint(covariant PricePainter oldDelegate) =>
      oldDelegate.report != report;
}
