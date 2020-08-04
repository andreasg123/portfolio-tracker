import Foundation

class MockURLSession: URLSessionProtocol {
    var data: Data?
    var error: Error?
    var statusCode: Int?

    func dataTask(with url: URL, completionHandler: @escaping (Data?, URLResponse?, Error?) -> Void) -> URLSessionDataTask {
        print("MockURLSession.dataTask")
        let data = self.data
        let error = self.error
        let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)
        return MockURLSessionDataTask {
            completionHandler(data, response, error)
        }
    }
}

class MockURLSessionDataTask: URLSessionDataTask {
    private let completionHandler: () -> Void

    init(completionHandler: @escaping () -> Void) {
        self.completionHandler = completionHandler
    }

    override func resume() {
        print("MockURLSessionDataTask.resume")
        completionHandler()
    }
}

class MockUserDefaults: UserDefaults {
    override func string(forKey defaultName: String) -> String? {
        switch defaultName {
        case "url":
            return "https://example.com/"
        case "user":
            return "test"
        case "password":
            return "pw"
        default:
            return nil
        }
    }
}
