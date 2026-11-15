import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'master_reference.dart';

const riskAssumption =
    '계획상 보호 수익은 지정 손절가에 체결된다는 가정에 따른 예상값입니다. 갭하락, 슬리피지, 거래정지 등으로 실제 결과는 달라질 수 있습니다.';
String riskValue(dynamic n, [String unit = 'R']) =>
    n == null ? '기준 정보 부족' : '${(n as num).toStringAsFixed(2)}$unit';

class PositionRiskWorkspace extends StatefulWidget {
  final TradingApi? api;
  final bool statisticsOnly;
  final int legacyCount;
  const PositionRiskWorkspace({
    super.key,
    this.api,
    this.statisticsOnly = false,
    this.legacyCount = 0,
  });
  @override
  State<PositionRiskWorkspace> createState() => _PositionRiskWorkspaceState();
}

class _PositionRiskWorkspaceState extends State<PositionRiskWorkspace>
    with WidgetsBindingObserver {
  Map<String, dynamic>? data;
  String? selected, error;
  bool busy = false;
  Timer? refreshTimer;
  @override
  void initState() {
    super.initState();
    widget.api?.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => load());
    load();
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    widget.api?.removeListener(changed);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      load();
    }
  }

  void changed() {
    load();
  }

  Future<void> load() async {
    if (widget.api == null) return;
    try {
      final result = Map<String, dynamic>.from(
        await widget.api!.request('/api/positions'),
      );
      if (mounted) {
        setState(() {
          data = result;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  Future<void> input(
    String title,
    Map<String, String> fields,
    Future<void> Function(Map<String, String>) submit,
  ) async {
    final controllers = fields.map(
      (k, v) => MapEntry(k, TextEditingController(text: v)),
    );
    bool saving = false;
    String? problem;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialog) => AlertDialog(
          title: Text(title),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final entry in controllers.entries)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: TextField(
                        controller: entry.value,
                        enabled: !saving,
                        decoration: InputDecoration(labelText: entry.key),
                        keyboardType:
                            entry.key.contains('수량') ||
                                entry.key.contains('가격') ||
                                entry.key.contains('손절') ||
                                entry.key.contains('수수료')
                            ? const TextInputType.numberWithOptions(
                                decimal: true,
                              )
                            : TextInputType.text,
                      ),
                    ),
                  if (problem != null)
                    Text(problem!, style: const TextStyle(color: masterRed)),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.pop(context),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      setDialog(() => saving = true);
                      try {
                        await submit(
                          controllers.map((k, v) => MapEntry(k, v.text.trim())),
                        );
                        if (context.mounted) Navigator.pop(context);
                      } catch (e) {
                        if (context.mounted) {
                          setDialog(() {
                            problem = e.toString().replaceFirst(
                              'Exception: ',
                              '',
                            );
                            saving = false;
                          });
                        }
                      }
                    },
              child: Text(saving ? '저장 중…' : '저장'),
            ),
          ],
        ),
      ),
    );
    // Controllers are disposed after the dialog route has finished its exit animation.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    for (final c in controllers.values) {
      c.dispose();
    }
  }

  Future<void> action(
    Map<String, dynamic>? cycle,
    String type,
    Map<String, dynamic> values,
  ) async {
    final actionId =
        values['actionId'] ?? 'A_${DateTime.now().microsecondsSinceEpoch}';
    final id = cycle?['id'] ?? 'C_$actionId';
    setState(() => busy = true);
    try {
      await widget.api!.request(
        '/api/positions/$id/action',
        method: 'POST',
        body: {
          'type': type,
          'actionId': actionId,
          'version': cycle?['version'] ?? 0,
          'at': DateTime.now().toUtc().toIso8601String(),
          ...values,
        },
      );
      selected = id;
      await load();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void buy(Map<String, dynamic>? cycle) {
    input(
      cycle == null ? '새 매매 사이클 · 최초 매수' : '추가 매수 체결',
      {
        if (cycle == null) '종목명': '',
        if (cycle == null) '종목코드 (선택)': '',
        '주문 ID (중복 방지)': 'A_${DateTime.now().microsecondsSinceEpoch}',
        '매수 가격': '',
        '매수 수량': '',
        '손절가 (없으면 기준 정보 부족)': '',
        '수수료': '0',
        '체결 일시 (시간대 포함)': DateTime.now().toUtc().toIso8601String(),
        '매수 사유': '',
      },
      (v) => action(cycle, 'buy', {
        if (cycle == null) 'ticker': v['종목명'],
        if (cycle == null) 'code': v['종목코드 (선택)'],
        'actionId': v['주문 ID (중복 방지)'],
        'price': v['매수 가격'],
        'quantity': v['매수 수량'],
        'stop': v['손절가 (없으면 기준 정보 부족)'],
        'fee': v['수수료'],
        'at': v['체결 일시 (시간대 포함)'],
        'memo': v['매수 사유'],
      }),
    );
  }

  void sell(Map<String, dynamic> c) {
    final lots = (c['lots'] as List)
        .where((l) => (l['remaining'] as num) > 0)
        .toList();
    input(
      '차수별 매도 배분',
      {
        '주문 ID (중복 방지)': 'A_${DateTime.now().microsecondsSinceEpoch}',
        '매도 가격': '',
        '수수료': '0',
        '체결 일시 (시간대 포함)': DateTime.now().toUtc().toIso8601String(),
        for (int i = 0; i < lots.length; i++)
          '${i + 1}차 매도 수량 (보유 ${lots[i]['remaining']})': '0',
      },
      (v) => action(c, 'sell', {
        'actionId': v['주문 ID (중복 방지)'],
        'price': v['매도 가격'],
        'fee': v['수수료'],
        'at': v['체결 일시 (시간대 포함)'],
        'allocations': [
          for (int i = 0; i < lots.length; i++)
            if (num.tryParse(
                  v['${i + 1}차 매도 수량 (보유 ${lots[i]['remaining']})'] ?? '',
                ) !=
                0)
              {
                'lotId': lots[i]['id'],
                'quantity': v['${i + 1}차 매도 수량 (보유 ${lots[i]['remaining']})'],
              },
        ],
      }),
    );
  }

  void settings() {
    final r = Map<String, dynamic>.from(data!['rules']);
    input(
      '실험용 위험 규칙 · 책의 공식 기준이 아닙니다',
      {
        '최대 E': '${r['maxE']}',
        '최대 CR': '${r['maxCR']}',
        '보호 조건 시작 R': '${r['protectAtR']}',
        '최소 보호 수익 R': '${r['minProtectedR']}',
        '초기 위험 한도 (%)': '${r['initialRiskPercent']}',
        '계좌 평가액 (선택)': '${r['accountValue']}',
      },
      (v) async {
        await widget.api!.request(
          '/api/positions/rules',
          method: 'PUT',
          body: {
            ...r,
            'maxE': v['최대 E'],
            'maxCR': v['최대 CR'],
            'protectAtR': v['보호 조건 시작 R'],
            'minProtectedR': v['최소 보호 수익 R'],
            'initialRiskPercent': v['초기 위험 한도 (%)'],
            'accountValue': v['계좌 평가액 (선택)'],
          },
        );
        await load();
      },
    );
  }

  Widget panel(String title, Widget body, {String? caption}) => MasterPanel(
    title: title,
    caption: caption,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      child: body,
    ),
  );
  Widget stats() {
    final s = Map<String, dynamic>.from(data!['statistics']);
    Widget comparison(String title, Map v) => panel(
      title,
      Text(
        '${v['count']}건 · 평균 ${riskValue(v['averageR'])} · 누적 ${riskValue(v['totalR'])}',
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        panel(
          '최초 위험 기준 R 성과',
          muted(
            '전량 청산되고 최초 R이 확정된 사이클만 집계합니다. 손익 0인 거래는 전체 건수에 포함하며 승리·패배에는 포함하지 않습니다. 기대값은 승률 × 평균 수익 R − 패배율 × 평균 손실 R 절댓값입니다. 기존 거래 ${widget.legacyCount}건은 기준 정보 부족으로 제외합니다.',
          ),
        ),
        cardGrid([
          MasterCard(label: '종료 거래', value: '${s['count']}건'),
          MasterCard(label: '총 누적 R', value: riskValue(s['totalR'])),
          MasterCard(label: '평균 거래 R', value: riskValue(s['averageR'])),
          MasterCard(label: '기대값', value: riskValue(s['expectancy'])),
          MasterCard(label: '평균 수익 R', value: riskValue(s['averageWinR'])),
          MasterCard(label: '평균 손실 R', value: riskValue(s['averageLossR'])),
          MasterCard(label: '승률', value: riskValue(s['winRate'], '%')),
          MasterCard(label: '손익 0', value: '${s['breakeven']}건'),
        ]),
        comparison('피라미딩 거래', s['pyramiding'] as Map),
        comparison('단일 진입 거래', s['single'] as Map),
        panel(
          '거래별 확정 R',
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final row in s['rows'] as List)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    '${row['ticker']} · ${riskValue(row['realizedR'])} · ${row['pyramiding'] == true ? '피라미딩' : '단일 진입'}',
                  ),
                ),
              if ((s['rows'] as List).isEmpty)
                muted('아직 R 기준이 있는 종료 거래가 없습니다.'),
            ],
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.api == null) {
      return panel(
        'R·CR·E 포지션 관리',
        muted(
          '본인 계정으로 로그인하면 실제 체결을 기록할 수 있습니다. 기존 거래는 최초 손절가·수량이 없어 기준 정보 부족으로 표시합니다.',
        ),
      );
    }
    if (data == null) {
      return panel(
        '포지션 저장소',
        Column(
          children: [
            if (error == null)
              const LinearProgressIndicator()
            else
              Text(error!, style: const TextStyle(color: masterRed)),
            TextButton(onPressed: load, child: const Text('다시 불러오기')),
          ],
        ),
      );
    }
    if (widget.statisticsOnly) return stats();
    final cycles = (data!['cycles'] as List).cast<Map<String, dynamic>>();
    final c =
        cycles.where((c) => c['id'] == selected).firstOrNull ??
        cycles.where((c) => c['closed'] == false).firstOrNull ??
        cycles.firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        panel(
          '포지션 · R / CR / E',
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              muted(
                '최초 1R과 최초 수량은 고정됩니다. 현재가는 직접 입력한 관측값이며 실시간 시세가 아닙니다. 수수료는 체결 시 실현손익에서 한 번 차감합니다.',
              ),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  FilledButton.icon(
                    onPressed: busy ? null : () => buy(null),
                    icon: const Icon(Icons.add),
                    label: const Text('새 매매 사이클'),
                  ),
                  OutlinedButton(
                    onPressed: settings,
                    child: const Text('위험 규칙'),
                  ),
                  TextButton(onPressed: load, child: const Text('새로고침')),
                ],
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('위험 경고 사용 (주문을 막지 않습니다)'),
                value: data!['rules']['enabled'] == true,
                onChanged: (value) async {
                  try {
                    await widget.api!.request(
                      '/api/positions/rules',
                      method: 'PUT',
                      body: {
                        ...Map<String, dynamic>.from(data!['rules']),
                        'enabled': value,
                      },
                    );
                    await load();
                  } catch (e) {
                    if (mounted) setState(() => error = e.toString());
                  }
                },
              ),
              if (error != null)
                Text(error!, style: const TextStyle(color: masterRed)),
              for (final row in cycles)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  selected: row['id'] == c?['id'],
                  title: Text(
                    '${row['ticker']} · ${row['closed'] == true ? '청산 완료' : '보유 중'}',
                  ),
                  subtitle: Text(
                    '${row['events'][0]['at']} · ${row['quantity']}주 · ${riskValue(row['totalR'])}',
                  ),
                  onTap: () => setState(() => selected = row['id'] as String),
                ),
              if (cycles.isEmpty)
                muted('기존 청산 거래는 임의 변환하지 않습니다. 새 매매의 최초 체결부터 기록하세요.'),
            ],
          ),
        ),
        if (c != null) ...[
          cardGrid([
            for (final entry in <String, dynamic>{
              '최초 1R 금액': c['initialR'] == null
                  ? '기준 정보 부족'
                  : masterWon(c['initialR'] as num),
              '현재 CR': riskValue(c['cr'], ' CR'),
              '현재 E': riskValue(c['e'], ' E'),
              '실현손익': riskValue(c['realizedR']),
              '미실현손익': riskValue(c['unrealizedR']),
              '총손익': riskValue(c['totalR']),
              '계획상 보호 수익': riskValue(c['protectedR']),
              '예상 반납': riskValue(c['givebackR']),
            }.entries)
              MasterCard(label: entry.key, value: entry.value as String),
          ]),
          panel(
            '수익 보호 · 현재 ${masterWon(c['mark'] as num)}',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '현재 총손익 ${masterWon(c['total'] as num)} · 손절 시 예상 최종 손익 ${c['protected'] == null ? '기준 정보 부족' : masterWon(c['protected'] as num)}',
                ),
                Text(
                  '예상 반납액 ${c['giveback'] == null ? '기준 정보 부족' : masterWon(c['giveback'] as num)} · 반납률 ${riskValue(c['givebackPercent'], '%')}',
                ),
                Text(
                  '관측 최고 총손익 ${masterWon(c['peak'] as num)} · 최근 추가 매수 이후 최고 ${c['pyramidPeak'] == null ? '없음' : masterWon(c['pyramidPeak'] as num)}',
                ),
                Text(
                  '최고 총손익 대비 현재 반납률 ${riskValue(c['peakGivebackPercent'], '%')}',
                ),
                muted('최고 손익은 입력·저장된 주가 관측값에 한정됩니다. CR=0이어도 평가수익 반납 위험은 남습니다.'),
                muted(riskAssumption),
                for (final warning in c['warnings'] as List)
                  Text('⚠ $warning', style: const TextStyle(color: masterRed)),
                if (c['closed'] == false)
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      OutlinedButton(
                        onPressed: busy
                            ? null
                            : () => input(
                                '현재가 관측 기록',
                                {'현재 가격': '${c['mark']}'},
                                (v) => action(c, 'mark', {'price': v['현재 가격']}),
                              ),
                        child: const Text('현재가 갱신'),
                      ),
                      OutlinedButton(
                        onPressed: busy ? null : () => buy(c),
                        child: const Text('추가 매수 체결'),
                      ),
                      OutlinedButton(
                        onPressed: busy ? null : () => sell(c),
                        child: const Text('차수별 매도'),
                      ),
                    ],
                  ),
                if (c['closed'] == true)
                  muted(
                    '최종 청산 기록이 거래 목록과 매매일지에 자동 연결됐습니다. 재진입은 새 매매 사이클로 등록하세요.',
                  ),
              ],
            ),
          ),
          panel(
            '매수 차수별 관리',
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final l in c['lots'] as List)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${(c['lots'] as List).indexOf(l) + 1}차 · ${l['at']}',
                        ),
                        Text(
                          '매수가 ${masterWon(l['price'] as num)} · 최초 ${l['initialQuantity']}주 / 잔여 ${l['remaining']}주',
                        ),
                        Text(
                          '손절 ${l['stop'] == null ? '미입력' : masterWon(l['stop'] as num)} · ${riskValue(l['cr'], ' CR')}',
                        ),
                        Text(
                          '실현 ${masterWon(l['realized'] as num)} · 미실현 ${masterWon(l['unrealized'] as num)} (차수 손익은 수수료 전)',
                        ),
                        if ('${l['memo']}'.isNotEmpty) muted('${l['memo']}'),
                        for (final h in l['history'] as List)
                          muted(
                            '${h['at']} · 손절 ${h['from'] ?? '미입력'} → ${h['to']}',
                          ),
                        if ((l['remaining'] as num) > 0)
                          TextButton(
                            onPressed: busy
                                ? null
                                : () => input(
                                    '차수 손절가 변경',
                                    {'새 손절가': '${l['stop'] ?? ''}'},
                                    (v) => action(c, 'stop', {
                                      'lotId': l['id'],
                                      'stop': v['새 손절가'],
                                    }),
                                  ),
                            child: const Text('손절가 변경'),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          if (c['closed'] == false)
            PyramidSimulator(
              key: ValueKey('${c['id']}_${c['version']}'),
              api: widget.api!,
              cycle: c,
            ),
          panel(
            '체결·변경 이력',
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final e in c['events'] as List)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text(
                      '${e['at']} · ${{'buy': '매수', 'sell': '매도', 'stop': '손절 변경', 'mark': '현재가 관측'}[e['type']]}${e['price'] == null ? '' : ' · ${e['price']}원'}${e['quantity'] == null ? '' : ' · ${e['quantity']}주'}${e['allocations'] == null ? '' : ' · 차수별 배분 ${e['allocations']}'}',
                    ),
                  ),
              ],
            ),
          ),
        ],
        stats(),
      ],
    );
  }
}

class PyramidSimulator extends StatefulWidget {
  final TradingApi api;
  final Map<String, dynamic> cycle;
  const PyramidSimulator({super.key, required this.api, required this.cycle});
  @override
  State<PyramidSimulator> createState() => _PyramidSimulatorState();
}

class _PyramidSimulatorState extends State<PyramidSimulator> {
  final price = TextEditingController(),
      quantity = TextEditingController(),
      stop = TextEditingController();
  final Map<String, TextEditingController> stops = {};
  Timer? timer;
  int requestId = 0;
  Map<String, dynamic>? result;
  String? error;
  @override
  void initState() {
    super.initState();
    for (final l in widget.cycle['lots'] as List) {
      if ((l['remaining'] as num) > 0) {
        stops[l['id'] as String] = TextEditingController(
          text: '${l['stop'] ?? ''}',
        );
      }
    }
    for (final c in [price, quantity, stop, ...stops.values]) {
      c.addListener(update);
    }
  }

  void update() {
    timer?.cancel();
    requestId++;
    setState(() => result = null);
    timer = Timer(const Duration(milliseconds: 300), calculate);
  }

  Future<void> calculate() async {
    if ([price, quantity, stop].any((c) => c.text.isEmpty)) return;
    final id = ++requestId;
    try {
      final value = await widget.api.request(
        '/api/positions/${widget.cycle['id']}/simulate',
        method: 'POST',
        body: {
          'price': price.text,
          'quantity': quantity.text,
          'stop': stop.text,
          'stops': [
            for (final s in stops.entries)
              if (s.value.text.isNotEmpty)
                {'lotId': s.key, 'stop': s.value.text},
          ],
        },
      );
      if (mounted && id == requestId) {
        setState(() {
          result = Map<String, dynamic>.from(value);
          error = null;
        });
      }
    } catch (e) {
      if (mounted && id == requestId) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    for (final c in [price, quantity, stop, ...stops.values]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MasterPanel(
    title: '추가 매수 전 위험 시뮬레이터',
    caption: '가상 계산만 수행하며 체결과 손절가는 저장하지 않습니다. 추가 매수가를 시나리오 현재가로 가정합니다.',
    child: Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final e in {
            '예상 추가 매수가': price,
            '추가 수량': quantity,
            '추가 물량 손절가': stop,
            ...{
              for (final s in stops.entries)
                '기존 ${(widget.cycle['lots'] as List).indexWhere((l) => l['id'] == s.key) + 1}차 손절 변경안':
                    s.value,
            },
          }.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: TextField(
                controller: e.value,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(labelText: e.key),
              ),
            ),
          if (error != null)
            Text(error!, style: const TextStyle(color: masterRed)),
          if (result != null) ...[
            for (final label in ['after', 'reduced'])
              if (result![label] != null)
                Builder(
                  builder: (context) {
                    final a = result![label] as Map,
                        b = result!['before'] as Map;
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            label == 'after' ? '입력 수량 추가 시' : '추가 수량 절반으로 줄이면',
                          ),
                          Text(
                            'E ${riskValue(b['e'], '')} → ${riskValue(a['e'], '')} · CR ${riskValue(b['cr'], '')} → ${riskValue(a['cr'], '')}',
                          ),
                          Text(
                            '현재 총손익 ${riskValue(b['totalR'])} → 추가 후 ${riskValue(a['totalR'])}',
                          ),
                          Text(
                            '손절 시 최종 ${riskValue(a['protectedR'])} · 예상 반납 ${a['giveback'] == null ? '정보 부족' : masterWon(a['giveback'] as num)} (${riskValue(a['givebackPercent'], '%')})',
                          ),
                          Text(
                            '전체 매수 누계 ${masterWon(a['totalInvested'] as num)} · 평가금액 ${masterWon(a['marketValue'] as num)} · 계좌 비중 ${riskValue(a['accountPercent'], '%')}',
                          ),
                          for (final w in a['warnings'] as List)
                            Text(
                              '⚠ $w',
                              style: const TextStyle(color: masterRed),
                            ),
                        ],
                      ),
                    );
                  },
                ),
            muted('경고는 의사결정 참고용이며 실제 매수를 금지하지 않습니다.'),
          ],
          muted(riskAssumption),
        ],
      ),
    ),
  );
}
