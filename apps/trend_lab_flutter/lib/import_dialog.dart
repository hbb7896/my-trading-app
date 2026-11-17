import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';

class ImportDialog extends StatefulWidget {
  final TradingApi api;
  const ImportDialog({super.key, required this.api});
  @override
  State<ImportDialog> createState() => _ImportDialogState();
}

class _ImportDialogState extends State<ImportDialog> {
  String? csv, name, error;
  Map<String, dynamic>? preview;
  bool busy = false;
  Future<void> pick() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final file = await openFile(
        acceptedTypeGroups: [
          const XTypeGroup(
            label: 'Trading Master CSV',
            extensions: ['csv'],
            mimeTypes: ['text/csv', 'text/plain'],
          ),
        ],
      );
      if (file == null) return;
      if (await file.length() > 2000000) throw Exception('CSV는 2MB 이하만 선택하세요.');
      final text = utf8.decode(await file.readAsBytes());
      final data = Map<String, dynamic>.from(
        await widget.api.request(
          '/api/import/preview',
          method: 'POST',
          body: {'csv': text},
        ),
      );
      if (mounted) {
        setState(() {
          csv = text;
          name = file.name;
          preview = data;
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
      final result = await widget.api.request(
        '/api/import/commit',
        method: 'POST',
        body: {'csv': csv},
      );
      if (mounted) {
        Navigator.pop(
          context,
          '${result['inserted']}건 가져옴 · ${result['skipped']}건 중복 제외',
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
    final rows = preview?['rows'] as List? ?? [],
        invalid = rows.where((r) => (r['issues'] as List).isNotEmpty).length;
    final missing = rows
        .where((r) => r['trade']['code'] == '' || r['trade']['entry'] == '')
        .length;
    return AlertDialog(
      title: const Text('Trading Master 기록 가져오기'),
      content: SizedBox(
        width: 650,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Trading Master의 내보내기 버튼으로 받은 CSV를 선택하세요. 기존 기록을 덮어쓰지 않으며, 같은 파일을 다시 가져와도 중복 저장하지 않습니다.',
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: busy ? null : pick,
                icon: const Icon(Icons.upload_file),
                label: Text(name ?? 'CSV 파일 선택'),
              ),
              if (busy) const LinearProgressIndicator(),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    error!,
                    style: const TextStyle(color: Colors.orangeAccent),
                  ),
                ),
              if (preview != null) ...[
                const SizedBox(height: 16),
                Text(
                  '전체 ${preview!['total']}건 · 새 기록 ${preview!['valid']}건 · 중복 ${preview!['duplicates']}건 · 오류 $invalid건',
                ),
                if (missing > 0)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      '$missing건은 진입일 또는 종목코드가 없습니다. 기록은 가져올 수 있고, 차트 복기 전에 거래 수정에서 보완하세요.',
                      style: const TextStyle(color: Colors.orangeAccent),
                    ),
                  ),
                for (final r in rows.take(50))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('${r['row']}행 · ${r['trade']['ticker']}'),
                    subtitle: Text(
                      '${r['trade']['entry']} → ${r['trade']['exit']}',
                    ),
                    trailing: Text(
                      (r['issues'] as List).isNotEmpty
                          ? (r['issues'] as List).join(', ')
                          : r['duplicate']
                          ? '중복'
                          : '가져오기',
                    ),
                  ),
                if (rows.length > 50)
                  const Text('미리보기는 처음 50건만 표시합니다. 가져오기는 전체 기록에 적용됩니다.'),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('닫기'),
        ),
        FilledButton(
          onPressed:
              busy || preview == null || invalid > 0 || preview!['valid'] == 0
              ? null
              : commit,
          child: const Text('확인한 기록 가져오기'),
        ),
      ],
    );
  }
}
