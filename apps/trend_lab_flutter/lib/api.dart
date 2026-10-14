import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'package:http/http.dart' as http;

import 'trade.dart';

class TradingApi extends ChangeNotifier {
  final String baseUrl, token;
  final String Function()? tokenProvider;
  TradingApi(this.baseUrl, this.token, {this.tokenProvider});
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'))
      ..headers.addAll({
        'Authorization': 'Bearer ${tokenProvider?.call() ?? token}',
        'Content-Type': 'application/json',
      });
    if (body != null) request.body = jsonEncode(body);
    try {
      final response = await http.Response.fromStream(
        await request.send().timeout(const Duration(seconds: 25)),
      );
      final data = jsonDecode(response.body);
      if (response.statusCode >= 400) {
        throw Exception(data['error'] ?? '서버 요청 실패');
      }
      if (method != 'GET' &&
          (path.startsWith('/api/trades') || path.endsWith('/commit'))) {
        notifyListeners();
      }
      return data;
    } on FormatException {
      throw Exception('API 서버 주소를 확인하세요.');
    }
  }

  Future<List<Trade>> trades() async => ((await request('/api/trades')) as List)
      .map((e) => Trade.fromJson(Map<String, dynamic>.from(e)))
      .toList();
  Future<void> save(Trade t) async {
    await request(
      t.id.isEmpty ? '/api/trades' : '/api/trades/${Uri.encodeComponent(t.id)}',
      method: t.id.isEmpty ? 'POST' : 'PUT',
      body: t.toJson(),
    );
  }

  Future<void> delete(Trade t) async {
    await request('/api/trades/${Uri.encodeComponent(t.id)}', method: 'DELETE');
  }

  Future<Trade> saveJournal(Trade value, Trade original) async {
    Map<String, dynamic> fields(Trade t) => {
      'memo': t.memo,
      'tags': t.extra['tags'] ?? <String>[],
      'emotion': t.extra['emotion'] ?? '',
      'discipline': t.extra['discipline'] ?? '',
      'chart_link': t.extra['chart_link'] ?? '',
    };
    final result = await request(
      '/api/trades/${Uri.encodeComponent(value.id)}/journal',
      method: 'PATCH',
      body: {...fields(value), 'original': fields(original)},
    );
    return Trade.fromJson(Map<String, dynamic>.from(result));
  }

  Future<Map<String, dynamic>> review(Trade t) async =>
      Map<String, dynamic>.from(
        await request('/api/review', method: 'POST', body: t.toJson()),
      );
}
