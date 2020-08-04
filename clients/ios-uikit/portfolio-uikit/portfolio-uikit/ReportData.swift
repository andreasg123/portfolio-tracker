struct ReportData: Decodable, Encodable {
    var account: String
    var accounts: [String: Account] = [:]
    var quotes: [String: Double] = [:]
}

struct Account: Decodable, Encodable {
    var cash: Double = 0
    var cash_diff: Double = 0
    var cash_like: Double = 0
    var cash_like_diff: Double = 0
    var deposits: [[Double]] = []
    var lots: [Lot] = []
    
}

struct Lot: Decodable, Encodable {
    var symbol: String
    var nshares: Double
}
