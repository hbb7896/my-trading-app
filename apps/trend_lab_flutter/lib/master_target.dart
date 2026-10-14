import 'package:flutter/material.dart';

import 'master_metrics.dart';
import 'master_reference.dart';

class TargetCalculator extends StatefulWidget {
  final MasterMetrics stats;
  const TargetCalculator({super.key, required this.stats});
  @override
  State<TargetCalculator> createState() => _TargetCalculatorState();
}

class _TargetCalculatorState extends State<TargetCalculator> {
  static const example = ['100000000', '25', '40', '14', '7', '46'];
  final inputs = example.map((s) => TextEditingController(text: s)).toList();
  String basis = '예시 가정';
  @override
  void dispose() {
    for (final c in inputs) {
      c.dispose();
    }
    super.dispose();
  }

  void apply() {
    setState(() {
      inputs[3].text = widget.stats.averageWin.toStringAsFixed(2);
      inputs[4].text = widget.stats.averageLoss.toStringAsFixed(2);
      inputs[5].text = widget.stats.winRate.toStringAsFixed(2);
      basis = '선택 연도의 기록 반영 · 비율은 소수 둘째 자리';
    });
  }

  Widget result(String label, String value, {String? sub, Color? color}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 13),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: muted(label, size: 13)),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    value,
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w500,
                      color: color,
                    ),
                  ),
                  if (sub != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        sub,
                        textAlign: TextAlign.right,
                        style: const TextStyle(
                          fontSize: 11,
                          color: masterMuted,
                          height: 1.7,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      );
  @override
  Widget build(BuildContext context) {
    final v = inputs.map((c) => double.tryParse(c.text)).toList();
    final valid =
        v.every((n) => n != null && n.isFinite) &&
        v[0]! > 0 &&
        v[0]! <= 1e15 &&
        v[1]! > 0 &&
        v[1]! <= 100 &&
        v[2]! >= 0 &&
        v[2]! <= 10000 &&
        v[3]! >= 0 &&
        v[3]! <= 10000 &&
        v[4]! >= 0 &&
        v[4]! <= 100 &&
        v[5]! >= 0 &&
        v[5]! <= 100;
    final r = valid
        ? TargetResult(
            portfolio: v[0]!,
            position: v[1]!,
            target: v[2]!,
            win: v[3]!,
            loss: v[4]!,
            success: v[5]!,
          )
        : null;
    return MasterPanel(
      title: '목표수익 달성',
      caption: '포지션 크기와 수익·손실 가정을 바꾸며 목표 달성에 필요한 거래수를 계산하세요.',
      action: const Icon(Icons.calculate_outlined, color: masterMint, size: 24),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 0, 22, 22),
        child: pair(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '입력',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
              muted(basis, size: 11),
              const SizedBox(height: 20),
              for (int i = 0; i < inputs.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 18),
                  child: TextField(
                    controller: inputs[i],
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: InputDecoration(
                      labelText: [
                        '포트폴리오 규모 (원)',
                        '포지션 비중 (%)',
                        '목표 수익률 (%)',
                        '평균 수익률 (%)',
                        '평균 손실률 (%)',
                        '수익 거래 비율 (승률 %)',
                      ][i],
                    ),
                    onChanged: (_) => setState(() => basis = '직접 입력한 가정'),
                  ),
                ),
              Wrap(
                spacing: 12,
                children: [
                  OutlinedButton.icon(
                    onPressed: widget.stats.n == 0 ? null : apply,
                    icon: const Icon(Icons.trending_up, size: 15),
                    label: const Text('내 기록 반영'),
                  ),
                  TextButton.icon(
                    onPressed: () => setState(() {
                      for (int i = 0; i < inputs.length; i++) {
                        inputs[i].text = example[i];
                      }
                      basis = '예시 가정';
                    }),
                    icon: const Icon(Icons.refresh, size: 14),
                    label: const Text('예시값'),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              muted(
                '초기 금액 1억원과 비율은 예시입니다. 실제 포트폴리오 규모를 입력하세요. ‘내 기록 반영’은 선택 연도의 평균 수익·손실과 승률만 불러옵니다.',
                size: 12,
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                '결과',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
              muted('고정 포지션 · 단순 기대값', size: 11),
              const SizedBox(height: 20),
              if (r == null)
                muted('금액과 비율의 범위를 확인해주세요.')
              else ...[
                Container(
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    color: const Color(0xff20372f),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      muted('목표 금액'),
                      const SizedBox(height: 10),
                      Text(
                        masterWon(r.targetAmount),
                        style: const TextStyle(
                          fontSize: 28,
                          color: masterMint,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 7),
                      muted('포트폴리오 대비 +${v[2]!.toStringAsFixed(2)}%', size: 12),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                result(
                  '포지션 규모',
                  masterWon(r.positionAmount),
                  sub: '포트폴리오의 ${v[1]!.toStringAsFixed(2)}%',
                ),
                result(
                  '수익 거래의 평균 수익',
                  masterWon(r.winAmount),
                  color: masterMint,
                ),
                result(
                  '손실 거래의 평균 손실',
                  masterWon(r.lossAmount),
                  color: masterRed,
                ),
                result('수익 / 손실 비율', '${ratio(r.rewardRisk)} : 1'),
                result(
                  '거래별 기대 수익률',
                  masterPct(r.expectancy),
                  color: masterSign(r.expectancy),
                ),
                result(
                  '거래별 기대 손익',
                  masterWon(r.positionAmount * r.expectancy / 100),
                  color: masterSign(r.expectancy),
                ),
                result(
                  '목표 달성 소요 거래수',
                  r.trades == null ? '산출 불가' : '${r.trades}건',
                ),
                result(
                  '예상 수익 / 손실 거래수',
                  r.trades == null
                      ? '—'
                      : '${(r.trades! * v[5]! / 100).toStringAsFixed(1)}건 / ${(r.trades! * (1 - v[5]! / 100)).toStringAsFixed(1)}건',
                  sub: '확률에 따른 기대 건수 · 확정 횟수가 아닙니다',
                ),
                result('조정 수익 / 손실 비율', '${ratio(r.adjustedRatio)} : 1'),
                result(
                  '켈리 비중 참고값',
                  r.kelly == null ? '—' : '${r.kelly!.toStringAsFixed(2)}%',
                  sub: '예상 수익률이 아닌 계산상 비중',
                ),
              ],
              const Divider(height: 28),
              muted(
                '포지션 금액을 매번 동일하게 유지하고 복리·동시 보유·회전 기간을 반영하지 않습니다. 수수료·세금은 입력한 수익·손실률에 포함된 만큼만 반영됩니다. 평균값과 승률이 유지된다는 가정의 결과이며 실제 목표 달성 거래수는 달라질 수 있습니다.',
                size: 12,
              ),
            ],
          ),
          left: 1,
        ),
      ),
    );
  }
}
