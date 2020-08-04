import Foundation

protocol DataRetrieverDelegate : AnyObject {
    func dataRetrieved(data: Data?, response: URLResponse?, error: Error?)
}
