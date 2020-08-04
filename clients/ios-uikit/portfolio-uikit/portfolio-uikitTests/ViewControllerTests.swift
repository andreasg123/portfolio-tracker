import XCTest
@testable import portfolio_uikit

class ViewControllerTests: XCTestCase {
    var sut: ViewController!
    var session: MockURLSession!

    override func setUp() {
        sut = UIStoryboard(name: "Main", bundle: Bundle(for: ViewController.self))
            .instantiateInitialViewController() as? ViewController
        sut.defaults = MockUserDefaults()
        session = MockURLSession()
        sut.retriever = DataRetriever(session: session)
        sut.retriever.delegate = sut
    }

    override func tearDown() {
        sut = nil
        session = nil
    }

    func testRetrieveData() throws {
        let quotes = ["AAPL": 436.89]
        let lots = [Lot(symbol: "AAPL", nshares: 500)]
        let account = Account(lots: lots)
        let report = ReportData(account: "ag-broker", accounts: ["ag-broker": account], quotes: quotes)
        session.data = try JSONEncoder().encode(report)
        sut.defaultsChanged()
        let expected = [["AAPL", "500.0", "436.89"]]
        XCTAssertEqual(sut.cellValues, expected)
    }
}
