import 'dart:async';
import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'trade.dart';
import 'master_journal.dart';
import 'master_metrics.dart';
import 'master_import.dart';
import 'master_reference.dart';
import 'master_sample.dart';

const masterSections = [
  '대시보드',
  '월별 성과',
  '연도별 성과',
  '거래 기록',
  'Trading DNA',
  '손익비 분석',
  'R-배수 분석',
  '손익 분포',
  '미너비니 지표',
  '미너비니 조언',
];
const mistakeTags = [
  '추격매수',
  '손절 지연',
  '조기청산',
  '과도한 포지션',
  '계획 없는 진입',
  '재진입 남발',
  '복수매매/뇌동매매',
  '진입 기준 미충족',
  '기타',
];

class TradingMasterScreen extends StatefulWidget {
  final TradingApi? api;
  final List<Trade> initialTrades;
  final bool preview;
  const TradingMasterScreen({
    super.key,
    this.api,
    this.initialTrades = const [],
    this.preview = false,
  });
  @override
  State<TradingMasterScreen> createState() => _TradingMasterScreenState();
}

class _TradingMasterScreenState extends State<TradingMasterScreen>
    with WidgetsBindingObserver {
  late TradingApi? api;
  late List<Trade> trades;
  Timer? timer;
  bool loading = false;
  String? error;
  int section = 0, days = 0;
  String query = '';
  bool demo = false;
  Trade? selectedJournal;
  @override
  void initState() {
    super.initState();
    api = widget.api;
    api?.addListener(sharedRecordsChanged);
    trades = widget.initialTrades;
    demo = trades.isEmpty;
    WidgetsBinding.instance.addObserver(this);
    if (api != null) Future.microtask(refresh);
    timer = Timer.periodic(const Duration(seconds: 30), (_) => refresh());
  }

  @override
  void dispose() {
    api?.removeListener(sharedRecordsChanged);
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void sharedRecordsChanged() => refresh();

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  void notify(Object e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  Future<void> refresh() async {
    if (api == null || loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final rows = await api!.trades();
      if (mounted) {
        setState(() {
          trades = rows;
          if (rows.isNotEmpty) demo = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> connect() async {
    if (widget.preview) {
      notify('화면 비교용 샘플 미리보기입니다. 실제 기록은 본인 로그인 후 사용할 수 있습니다.');
      return;
    }
    final url = TextEditingController(
      text: const String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'http://127.0.0.1:8787',
      ),
    );
    final key = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('로컬 미리보기 연결'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: url,
                decoration: const InputDecoration(labelText: '서버 주소'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: key,
                obscureText: true,
                decoration: const InputDecoration(labelText: '개인 연결 키'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('연결'),
          ),
        ],
      ),
    );
    if (accepted == true && mounted) {
      final u = Uri.tryParse(url.text.trim());
      if (u == null ||
          !['http', 'https'].contains(u.scheme) ||
          u.host.isEmpty ||
          u.userInfo.isNotEmpty ||
          u.query.isNotEmpty ||
          u.fragment.isNotEmpty ||
          key.text.length < 24) {
        notify('서버 주소와 24자 이상의 연결 키를 확인하세요.');
      } else {
        setState(
          () => api = TradingApi(
            url.text.trim().replaceAll(RegExp(r'/+$'), ''),
            key.text,
          ),
        );
        await refresh();
      }
    }
    url.dispose();
    key.dispose();
  }

  Future<void> edit([Trade? t]) async {
    if (t?.id.startsWith('DEMO_') == true) {
      notify('샘플 거래는 수정할 수 없습니다. 새 거래를 등록해주세요.');
      return;
    }
    if (api == null && !widget.preview) {
      await connect();
      return;
    }
    final value = await showDialog<Trade>(
      context: context,
      builder: (_) => MasterTradeForm(trade: t, onDelete: remove),
    );
    if (value != null) {
      if (api == null) {
        notify('샘플 미리보기에서는 실제 기록을 저장하지 않습니다.');
        return;
      }
      try {
        await api!.save(value);
        await refresh();
      } catch (e) {
        notify(e);
      }
    }
  }

  Future<void> journal(Trade t) async {
    setState(() => selectedJournal = t);
  }

  Future<void> remove(Trade t) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('거래 삭제'),
        content: Text('${t.ticker} 기록을 영구 삭제할까요?'),
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
    if (yes == true && api != null) {
      try {
        await api!.delete(t);
        await refresh();
      } catch (e) {
        notify(e);
      }
    }
  }

  Future<void> importRecords() async {
    if (api == null && !widget.preview) {
      await connect();
      return;
    }
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => MasterImportDialog(api: api),
    );
    if (result != null) {
      await refresh();
      notify(result);
    }
  }

  Future<void> export(List<Trade> rows) async {
    try {
      final file = XFile.fromData(
        Uint8List.fromList(utf8.encode(masterCsv(rows))),
        mimeType: 'text/csv',
        name: 'trading-master.csv',
      );
      if (kIsWeb) {
        await file.saveTo('trading-master.csv');
      } else if (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS) {
        await Clipboard.setData(ClipboardData(text: masterCsv(rows)));
        notify('CSV ${rows.length}건을 복사했습니다. 시트나 파일 앱에 붙여넣으세요.');
        return;
      } else {
        final location = await getSaveLocation(
          suggestedName: 'trading-master.csv',
        );
        if (location == null) return;
        await file.saveTo(location.path);
      }
      notify('현재 선택한 ${rows.length}건을 내보냈습니다.');
    } catch (e) {
      notify('내보내기를 완료하지 못했습니다: $e');
    }
  }

  List<Trade> get filtered {
    final now = DateTime.now().toUtc().add(const Duration(hours: 9));
    final cutoff = DateTime.utc(
      now.year,
      now.month,
      now.day,
    ).subtract(Duration(days: days));
    return (demo ? masterSample() : trades).where((t) {
      final date = DateTime.tryParse(t.exit);
      return days == 0 || (date != null && !date.isBefore(cutoff));
    }).toList();
  }

  Future<void> settings() async {
    await showDialog<void>(
      context: context,
      builder: (c) => StatefulBuilder(
        builder: (c, update) => AlertDialog(
          title: const Text('저널 설정'),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'WORKSPACE SETTINGS',
                  style: TextStyle(
                    color: masterMint,
                    letterSpacing: 1.5,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 20),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('샘플 데이터'),
                  subtitle: const Text('실제 기록과 분리된 미리보기입니다.'),
                  value: demo,
                  onChanged: (v) {
                    setState(() => demo = v);
                    update(() {});
                  },
                ),
                const Divider(),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('거래 기록 저장'),
                  subtitle: Text(
                    widget.preview
                        ? '화면 비교용 미리보기 · 샘플은 저장하지 않습니다.'
                        : api != null
                        ? '본인 계정의 온라인 저장소에 보관합니다.'
                        : '로그인 서버 연결이 필요합니다.',
                  ),
                  trailing: const Icon(
                    Icons.verified_user_outlined,
                    color: masterMint,
                  ),
                ),
                const SizedBox(height: 18),
                muted(
                  'Google Sheets 자동 연동은 아직 연결되지 않았습니다. 내보내기 파일은 원본 코드의 열 구조를 따릅니다.',
                ),
              ],
            ),
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(c),
              child: const Text('설정 완료'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ReferenceMaster(
    trades: filtered,
    section: section,
    days: days,
    demo: demo,
    loading: loading,
    connected: api != null,
    error: error,
    query: query,
    onSection: (v) => setState(() {
      section = v;
      query = '';
      selectedJournal = null;
    }),
    onDays: (v) => setState(() => days = v),
    onSearch: (v) => setState(() => query = v),
    onNew: () => edit(),
    onImport: importRecords,
    onExport: () => export(demo ? masterSample() : trades),
    onRefresh: refresh,
    onSettings: settings,
    onReal: () => setState(() => demo = false),
    onJournal: journal,
    onEdit: edit,
    journal: selectedJournal == null
        ? null
        : MasterJournalPage(
            key: ValueKey(selectedJournal!.id),
            trade: selectedJournal!,
            onBack: () => setState(() {
              selectedJournal = null;
              section = 0;
            }),
            onEdit: edit,
            onSave: (value) async {
              if (api == null) throw Exception('본인 계정으로 로그인한 후 저장할 수 있습니다.');
              final updated = await api!.saveJournal(value, selectedJournal!);
              if (mounted) setState(() => selectedJournal = updated);
              await refresh();
            },
          ),
  );
}
