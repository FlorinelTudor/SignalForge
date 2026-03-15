from tradeflow_bot.news import score_sentiment


def test_score_sentiment_positive_vs_negative():
    positive = score_sentiment("Company beats earnings and shows strong growth")
    negative = score_sentiment("Company misses targets and warns of losses")

    assert positive > 0
    assert negative < 0
