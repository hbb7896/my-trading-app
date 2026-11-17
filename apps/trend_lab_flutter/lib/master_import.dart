import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'master_reference.dart';

class MasterImportDialog extends StatefulWidget {
  final TradingApi? api;
  const MasterImportDialog({super.key, this.api});
  @override
  State<MasterImportDialog> createState() => _MasterImportDialogState();
}

class _MasterImportDialogState extends State<MasterImportDialog> {
  String? name, data, error;
  Map<String, dynamic>? report;
  int stage = 0;
  bool busy = false, accepted = false, fees = true, reverse = false;
  Future<void> pick() async {
    if (widget.api == null) {
      setState(() => error = '실제 파일을 가져오려면 본인 계정으로 로그인하세요.');
      return;
    }
    try {
      final file = await openFile(
        acceptedTypeGroups: const [
          XTypeGroup(
            label: '키움 거래내역',
            extensions: ['xlsx', 'xls', 'csv'],
            mimeTypes: [
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              'application/vnd.ms-excel',
              'text/csv',
            ],
          ),
        ],
      );
      if (file == null) return;
      if (await file.length() > 5 * 1024 * 1024) {
        throw Exception('파일은 5MB 이하로 나눠주세요.');
      }
      name = file.name;
      data = base64Encode(await file.readAsBytes());
      await preview(reset: true);
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    }
  }

  Future<void> preview({
    bool reset = false,
    String? sheet,
    int? header,
    Map<String, dynamic>? mapping,
    String? mode,
  }) async {
    setState(() {
      busy = true;
      error = null;
      accepted = false;
    });
    try {
      final value = await widget.api!.request(
        '/api/workbook/preview',
        method: 'POST',
        body: {
          'name': name,
          'data': data,
          if (sheet != null || !reset) 'sheet': sheet ?? report?['sheet'],
          if (!reset) 'header': header ?? report?['header'],
          if (!reset) 'map': mapping ?? report?['mapping'],
          if (!reset) 'mode': mode ?? report?['mode'],
          'fees': fees,
          'reverseSameDay': reverse,
        },
      );
      if (mounted) {
        setState(() {
          report = Map<String, dynamic>.from(value);
          stage = 1;
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

  Future<void> commit() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = await widget.api!.request(
        '/api/import/commit',
        method: 'POST',
        body: {'csv': report!['csv']},
      );
      if (mounted) {
        Navigator.pop(
          context,
          '${value['inserted']}건 신규 등록 · ${value['skipped']}건 중복 제외',
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
  Widget build(BuildContext context) {
    final rows = report?['rows'] as List? ?? [],
        headers = report?['headers'] as List? ?? [],
        issues = report?['issues'] as List? ?? [],
        missing = report?['missing'] as List? ?? [];
    final mode = report?['mode'] ?? 'summary';
    final visible = mode == 'summary'
        ? ['ticker', 'exit', 'entry', 'buy', 'sell', 'pnl', 'memo']
        : [
            'ticker',
            'code',
            'account',
            'exit',
            'side',
            'time',
            'qty',
            'amount',
            'price',
            'fee',
            'tax',
          ];
    final valid = rows
        .where((r) => (r['issues'] as List).isEmpty && !r['duplicate'])
        .length;
    return AlertDialog(
      title: Row(
        children: [
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'IMPORT YOUR TRADES',
                  style: TextStyle(
                    fontSize: 11,
                    letterSpacing: 1.5,
                    color: masterMint,
                  ),
                ),
                SizedBox(height: 8),
                Text('키움 거래내역 가져오기'),
              ],
            ),
          ),
          IconButton(
            tooltip: '가져오기 닫기',
            onPressed: busy ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
        ],
      ),
      content: SizedBox(
        width: 850,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              muted('엑셀 파일을 확인하고 과거 거래를 한 번에 등록하세요.'),
              const SizedBox(height: 20),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  for (int i = 0; i < 3; i++)
                    Text(
                      '${i + 1}  ${['파일 선택', '열 확인', '등록 미리보기'][i]}',
                      style: TextStyle(
                        fontSize: 13,
                        color: stage >= i ? masterMint : masterMuted,
                      ),
                    ),
                ],
              ),
              const Divider(height: 32),
              if (busy) const LinearProgressIndicator(),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(error!, style: const TextStyle(color: masterRed)),
                ),
              if (stage == 0) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    vertical: 30,
                    horizontal: 18,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xff182d31),
                    border: Border.all(color: const Color(0xff567067)),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    children: [
                      const Icon(
                        Icons.table_chart_outlined,
                        size: 44,
                        color: masterMint,
                      ),
                      const SizedBox(height: 18),
                      const Text(
                        '엑셀 파일을 선택하세요',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 12),
                      muted('키움증권에서 내려받은 .xlsx · .xls · .csv'),
                      const SizedBox(height: 18),
                      OutlinedButton.icon(
                        onPressed: busy ? null : pick,
                        icon: const Icon(Icons.upload_file, size: 18),
                        label: const Text('파일 선택'),
                      ),
                      const SizedBox(height: 14),
                      muted('최대 5MB · 거래내역 5,000행 · 암호가 없는 파일', size: 12),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                const Text('이런 내역을 불러올 수 있습니다'),
                const SizedBox(height: 10),
                muted(
                  '실현손익 내역: 종목명, 청산일, 매수금액, 매도금액 또는 실현손익\n체결 내역: 종목명, 거래일, 매수·매도 구분, 수량, 체결금액 또는 단가\n원본 파일은 서버에 보관하지 않습니다. 확인한 거래 정보만 저장합니다.',
                ),
              ],
              if (stage == 1 && report != null) ...[
                Row(
                  children: [
                    const Icon(
                      Icons.table_chart_outlined,
                      color: masterMint,
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(name ?? '')),
                    TextButton(
                      onPressed: busy ? null : () => setState(() => stage = 0),
                      child: const Text('다른 파일'),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                DropdownButtonFormField<String>(
                  initialValue: report!['sheet'],
                  decoration: const InputDecoration(labelText: '시트'),
                  items: [
                    for (final s in report!['sheetNames'] as List)
                      DropdownMenuItem(value: s as String, child: Text(s)),
                  ],
                  onChanged: busy
                      ? null
                      : (s) => preview(reset: true, sheet: s),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<int>(
                  key: ValueKey('${report!['sheet']}-${report!['header']}'),
                  initialValue: report!['header'] as int,
                  decoration: const InputDecoration(labelText: '제목 행'),
                  items: [
                    for (int i = 0; i < (report!['matrix'] as List).length; i++)
                      DropdownMenuItem(value: i, child: Text('${i + 1}행')),
                  ],
                  onChanged: busy
                      ? null
                      : (v) => preview(header: v, mapping: {}),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  key: ValueKey(mode),
                  initialValue: mode,
                  decoration: const InputDecoration(labelText: '거래내역 종류'),
                  items: const [
                    DropdownMenuItem(value: 'summary', child: Text('실현손익 내역')),
                    DropdownMenuItem(
                      value: 'executions',
                      child: Text('체결 내역 (선입선출 FIFO)'),
                    ),
                  ],
                  onChanged: busy ? null : (s) => preview(mode: s),
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (c, s) {
                    final width = s.maxWidth < 600
                        ? s.maxWidth
                        : (s.maxWidth - 16) / 2;
                    return Wrap(
                      spacing: 16,
                      runSpacing: 14,
                      children: [
                        for (final field in report!['fields'] as List)
                          if (visible.contains(field['key']))
                            SizedBox(
                              width: width,
                              child: DropdownButtonFormField<int>(
                                key: ValueKey(
                                  '${field['key']}-${report!['mapping'][field['key']]}',
                                ),
                                initialValue:
                                    (report!['mapping'][field['key']]
                                        as int?) ??
                                    -1,
                                isExpanded: true,
                                decoration: InputDecoration(
                                  labelText: field['label'],
                                ),
                                items: [
                                  const DropdownMenuItem(
                                    value: -1,
                                    child: Text('연결 안 함'),
                                  ),
                                  for (int i = 0; i < headers.length; i++)
                                    DropdownMenuItem(
                                      value: i,
                                      child: Text(
                                        '${i + 1}. ${headers[i]}',
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                ],
                                onChanged: busy
                                    ? null
                                    : (v) {
                                        final map = Map<String, dynamic>.from(
                                          report!['mapping'],
                                        );
                                        map[field['key']] = v;
                                        preview(mapping: map);
                                      },
                              ),
                            ),
                      ],
                    );
                  },
                ),
                if (mode == 'executions') ...[
                  CheckboxListTile(
                    value: fees,
                    onChanged: busy
                        ? null
                        : (v) {
                            setState(() => fees = v!);
                            preview();
                          },
                    title: const Text('수수료·세금 반영'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  CheckboxListTile(
                    value: reverse,
                    onChanged: busy
                        ? null
                        : (v) {
                            setState(() => reverse = v!);
                            preview();
                          },
                    title: const Text('같은 날 체결 순서를 역순으로 읽기'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ],
                if (missing.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: Text(
                      '필수 열을 연결하세요: ${missing.join(', ')}',
                      style: const TextStyle(color: masterRed),
                    ),
                  ),
                const SizedBox(height: 20),
                horizontalTable(headers.map((h) => h.toString()).toList(), [
                  for (final row
                      in (report!['matrix'] as List)
                          .skip((report!['header'] as int) + 1)
                          .take(5))
                    [
                      for (int i = 0; i < headers.length; i++)
                        i < (row as List).length ? row[i].toString() : '',
                    ],
                ]),
              ],
              if (stage == 2 && report != null) ...[
                Text(
                  '${rows.length}건의 거래 · 새 기록 $valid건 · 중복 ${rows.where((r) => r['duplicate']).length}건',
                ),
                const SizedBox(height: 16),
                if (report!['openQty'] > 0)
                  muted(
                    '파일 끝에 남은 보유 수량 ${report!['openQty']}주는 완료 거래에 포함하지 않습니다.',
                  ),
                if (issues.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(16),
                    color: const Color(0xff35352b),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '제외한 행을 확인하세요',
                          style: TextStyle(color: Color(0xffd1c59e)),
                        ),
                        for (final i in issues.take(20))
                          muted('${i['line']}행 · ${i['message']}'),
                      ],
                    ),
                  ),
                const SizedBox(height: 16),
                horizontalTable(
                  ['종목', '진입일', '청산일', '매수금액', '매도금액', '손익', '확인'],
                  [
                    for (final r in rows.take(100))
                      [
                        r['trade']['ticker'],
                        r['trade']['entry'],
                        r['trade']['exit'],
                        masterWon(r['trade']['buy']),
                        masterWon(r['trade']['sell']),
                        masterWon(r['trade']['sell'] - r['trade']['buy']),
                        r['duplicate']
                            ? '중복'
                            : (r['issues'] as List).isEmpty
                            ? '등록 가능'
                            : (r['issues'] as List).join(', '),
                      ],
                  ],
                ),
                CheckboxListTile(
                  value: accepted,
                  onChanged: busy ? null : (v) => setState(() => accepted = v!),
                  title: const Text('미리보기 금액과 제외한 행을 확인했습니다.'),
                  controlAffinity: ListTileControlAffinity.leading,
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        if (stage == 1)
          FilledButton(
            onPressed: busy || missing.isNotEmpty || rows.isEmpty
                ? null
                : () => setState(() => stage = 2),
            child: const Text('등록 미리보기'),
          ),
        if (stage == 2) ...[
          TextButton(
            onPressed: busy ? null : () => setState(() => stage = 1),
            child: const Text('열 연결 수정'),
          ),
          FilledButton.icon(
            onPressed:
                busy ||
                    !accepted ||
                    valid == 0 ||
                    rows.any((r) => (r['issues'] as List).isNotEmpty)
                ? null
                : commit,
            icon: const Icon(Icons.check, size: 17),
            label: Text(busy ? '등록 중…' : '$valid건 등록하기'),
          ),
        ],
      ],
    );
  }
}
