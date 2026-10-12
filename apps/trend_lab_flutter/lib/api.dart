import 'dart:convert';

import 'package:http/http.dart' as http;

import 'trade.dart';

class TradingApi {
  final String baseUrl, token;
  TradingApi(this.baseUrl, this.token);
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'))
      ..headers.addAll({
        'Authorization': 'Bearer $token',
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

  Future<Map<String, dynamic>> review(Trade t) async =>
      Map<String, dynamic>.from(
        await request('/api/review', method: 'POST', body: t.toJson()),
      );
}
