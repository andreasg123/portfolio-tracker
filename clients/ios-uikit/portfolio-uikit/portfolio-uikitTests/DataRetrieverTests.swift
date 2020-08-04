import XCTest
@testable import portfolio_uikit

class DataRetrieverTests: XCTestCase {
    var sut: MockURLSession!
    
    override func setUp() {
        sut = MockURLSession()
    }

    override func tearDown() {
        sut = nil
    }

    func testRetrieveData() throws {
        let expectation = DataRetrieverExpectation(description: "Retrieve data")
        sut.data = Data(count: 1)
        let retriever = DataRetriever(session: sut)
        retriever.delegate = expectation
        if let url = URL(string: "https://example.com/") {
            retriever.retrieveData(url: url, user: "test", password: "pw")
        }
        wait(for: [expectation], timeout: 10.0)
        XCTAssertNil(expectation.error, "error")
        if let response = expectation.response as? HTTPURLResponse {
            XCTAssertEqual(response.statusCode, 200, "response.statusCode")
        }
        else {
            XCTAssert(false, "response is HTTPURLResponse")
        }
    }
}


class DataRetrieverExpectation: XCTestExpectation, DataRetrieverDelegate {
    var data: Data?
    var response: URLResponse?
    var error: Error?

    func dataRetrieved(data: Data?, response: URLResponse?, error: Error?) {
        print("DataRetrieverExpectation.dataRetrieved")
        self.data = data
        self.response = response
        self.error = error
        fulfill()
    }
}
