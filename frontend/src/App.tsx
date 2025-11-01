import "./App.css";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { CommunicationPage } from "./pages/CommunicationPage";

const router = createBrowserRouter([
  {
    path: "/communication",
    element: <CommunicationPage />,
  },
]);

function App() {
  return (
    <>
      <main>
        <RouterProvider router={router} />
      </main>
    </>
  );
}

export default App;
