import UIKit

class ViewController: UIViewController {
    // Do not force unwrap to facilitate tests
    @IBOutlet weak var tableView: UITableView?
    var cellValues: [[String]] = []
    var retriever = DataRetriever()
    // For mocking UserDefaults in tests
    var defaults = UserDefaults.standard

    override func viewDidLoad() {
        super.viewDidLoad()
        tableView?.dataSource = self
        retriever.delegate = self
        NotificationCenter.default.addObserver(self, selector: #selector(ViewController.defaultsChanged), name: UserDefaults.didChangeNotification, object: nil)
        defaultsChanged()
    }

    @objc func defaultsChanged() {
        let portfolio_url = defaults.string(forKey: "url") ?? ""
        let user = defaults.string(forKey: "user") ?? ""
        let password = defaults.string(forKey: "password") ?? ""
        print("defaultsChanged", portfolio_url, user, password)
        cellValues = []
        tableView?.reloadData()
        print(portfolio_url)
        if let url = URL(string: portfolio_url) {
            retriever.retrieveData(url: url, user: user, password: password)
        }
    }
}

// MARK: - DataRetrieverDelegate
extension ViewController: DataRetrieverDelegate {
    func dataRetrieved(data: Data?, response: URLResponse?, error: Error?) {
        print("ViewController.dataRetrieved")
        if let error = error {
            print("error", error.localizedDescription)
        }
        else if let response = response as? HTTPURLResponse,
            response.statusCode != 200 {
            print("status", response.statusCode)
        }
        else if let data = data,
            let response = response as? HTTPURLResponse,
            response.statusCode == 200,
            let values = convertData(data) {
            cellValues = values
            DispatchQueue.main.async {
                self.tableView?.reloadData()
            }
        }
    }

    func convertData(_ data: Data) -> [[String]]? {
        // The account name should be another preference but this suffices as a sample.
        if let report = try? JSONDecoder().decode(ReportData.self, from: data),
            let account = report.accounts["ag-broker"] {
            return account.lots.map{ [$0.symbol, String($0.nshares), String(report.quotes[$0.symbol] ?? 0.0)] }
        }
        return nil
    }
}

// MARK: - UITableViewDataSource
extension ViewController: UITableViewDataSource {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        return cellValues.count;
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "lotCell", for: indexPath) as! PortfolioTableViewCell
        let row = cellValues[indexPath.row]
        cell.symbolLabel.text = row[0]
        cell.nsharesLabel.text = row[1]
        cell.quoteLabel.text = row[2]
        return cell
    }
}
