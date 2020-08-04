import Foundation

class DataRetriever {
    weak var delegate: DataRetrieverDelegate?
    // For mocking URLSession in tests
    var session: URLSessionProtocol
    var dataTask: URLSessionDataTask?

    init(session: URLSessionProtocol = URLSession(configuration: .default)) {
        self.session = session
        // print("DataRetriever", type(of: self.session))
    }

    func retrieveData(url: URL, user: String = "", password: String = "") {
        dataTask?.cancel()
        var request = URLRequest(url: url)
        // print("url", url)
        if !user.isEmpty {
            let login = String(format: "%@:%@", user, password)
            let loginData = login.data(using: .utf8)!
            let base64 = loginData.base64EncodedString()
            request.setValue("Basic \(base64)", forHTTPHeaderField: "Authorization")
        }
        dataTask = session.dataTask(with: url) {[weak self] data, response, error in
            defer {
                self?.dataTask = nil
            }
            print("completed", url, data ?? "no data")
            self?.delegate?.dataRetrieved(data: data, response: response, error: error)
        }
        dataTask?.resume()
    }
}
