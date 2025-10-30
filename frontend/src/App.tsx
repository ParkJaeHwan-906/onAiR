import "./App.css";
import HomeSmall from "./components/HomeSmall";
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
      <HomeSmall />
      <RouterProvider router={router} />
    </>
  );
}

export default App;
